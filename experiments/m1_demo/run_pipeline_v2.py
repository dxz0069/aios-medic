#!/usr/bin/env python3
"""M1 全闭环流水线 v2：诊断 DAG → 修复-验证回环(≤3轮) → 报告。

用法（容器内，venv python）:
  python experiments/m1_demo/run_pipeline_v2.py --collection ws/fault.json \
      --mode concurrent --out ws [--gold F03]

阶段：
  A(调度器)  T0 Commander → T1..T4 四路分析(并行/串行) → T5 Diagnostician
  B(回环)    每轮: T6k Repairer(LLM决策) → 确定性执行 → 重新采集 → T7k Verifier
             未恢复则回环 Repairer（消息: VERIFIER→REPAIRER VERIFY_RESULT，双向交互）
  C          T8 Reporter → report.md

正确性口径：类目/组件对照金标签 + recovery_ok（验证通过）。
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from middleware import MessageBus, Scheduler, Task, Workspace  # noqa: E402

ANALYST_SOURCE = {"log_analyst": "log", "metric_analyst": "metric",
                  "proc_analyst": "proc", "net_analyst": "net"}
MAX_REPAIR_ROUNDS = 3
FLAGS = ("cpu", "memory", "disk", "network", "service")
_AGENTS: dict = {}


def load_agent(name: str):
    if name not in _AGENTS:
        cfg = json.loads((REPO / "agents" / name / "config.json").read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location(
            f"medic_agent_{name}", REPO / "agents" / name / cfg["build"]["entry"])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _AGENTS[name] = getattr(mod, cfg["build"]["module"])
    return _AGENTS[name]()


def run_collect(out_path: Path) -> dict:
    subprocess.run(["python3", str(REPO / "testbed/collect/collect.py"),
                    "--out", str(out_path)],
                   check=True, capture_output=True, timeout=60)
    return json.loads(out_path.read_text(encoding="utf-8"))


def run_repair_exec(action: str, target: str) -> dict:
    r = subprocess.run(["python3", str(REPO / "testbed/repair/actions.py"),
                        "--action", action, "--target", target or ""],
                       capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"action": action, "rc": r.returncode, "detail": r.stderr[:200], "refused": True}


def phase_a(collection: dict, sched: Scheduler, timeline: list) -> dict:
    alert = collection.get("alert", {})
    now_ts = alert.get("ts", "")
    tasks = [Task("T0", "commander", lambda _u: json.dumps(alert, ensure_ascii=False))]
    for i, (agent, src) in enumerate(ANALYST_SOURCE.items(), start=1):
        snippet = collection["sources"][src]
        tasks.append(Task(f"T{i}", agent,
                          lambda _u, s=src, sn=snippet, ts=now_ts: json.dumps(
                              {"source": s, "snippet": sn, "now_ts": ts}, ensure_ascii=False),
                          deps=("T0",)))

    def diag_input(up):
        diagnoses = {f"A{i}": up[f"T{i}"] for i in range(1, 5) if f"T{i}" in up}
        return json.dumps({"alert": alert, "diagnoses": diagnoses}, ensure_ascii=False)

    tasks.append(Task("T5", "diagnostician", diag_input,
                      deps=("T1", "T2", "T3", "T4")))
    out = sched.run(tasks, load_agent)
    timeline.extend(out["timeline"])
    return out["results"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--mode", choices=["serial", "concurrent"], default="concurrent")
    ap.add_argument("--out", default=str(REPO / "experiments/m1_demo/ws"))
    ap.add_argument("--gold", default=None)
    args = ap.parse_args()

    t_start = time.time()
    collection = json.loads(Path(args.collection).read_text(encoding="utf-8"))
    ws = Workspace(args.out, run_id=f"{args.mode}-v2-{time.strftime('%m%d%H%M%S')}")
    ws.write_json("collection.json", collection)
    bus = MessageBus(ws)
    sched = Scheduler(bus, mode=args.mode, max_workers=4)
    timeline: list = []

    # 阶段A：诊断
    results_a = phase_a(collection, sched, timeline)
    root_cause = results_a.get("T5", {}).get("result", {})
    for tid, res in results_a.items():
        ws.write_json(f"reports/{tid}_{res.get('agent_name', 'unknown')}.json", res)

    # 阶段B：修复-验证回环
    # 注：v2c 曾试验"Reporter 草稿与首轮修复并行"，实测报告生成长于修复验证链，
    # 反而拉长并发关键路径（整体提速 -1.9%），已回滚——负结果记录于 docs/设计实现文档。
    repair_actions, verify_results = [], []
    recovered, last_verify = False, None
    for k in range(1, MAX_REPAIR_ROUNDS + 1):
        r_input = json.dumps({"root_cause": root_cause, "alert": collection.get("alert", {}),
                              "last_verify": last_verify, "round": k}, ensure_ascii=False)
        out_r = sched.run([Task(f"T6_{k}", "repairer", lambda _u, ri=r_input: ri)], load_agent)
        timeline.extend(out_r["timeline"])
        decision = out_r["results"][f"T6_{k}"].get("result", {})
        ws.write_json(f"reports/T6_{k}_repairer.json", out_r["results"][f"T6_{k}"])

        exec_res = run_repair_exec(decision.get("action", "none"),
                                   decision.get("target", ""))
        bus.emit("REPAIRER", "VERIFIER", "REPAIR_EXEC", exec_res, round_=k)
        repair_actions.append({"decision": decision, "exec": exec_res})

        fresh = run_collect(ws.path(f"verify_collect_{k}.json"))
        v_input = json.dumps({"alert_before": collection.get("alert", {}),
                              "alert_after": fresh.get("alert", {})}, ensure_ascii=False)
        out_v = sched.run([Task(f"T7_{k}", "verifier", lambda _u, vi=v_input: vi)], load_agent)
        timeline.extend(out_v["timeline"])
        last_verify = out_v["results"][f"T7_{k}"]
        ws.write_json(f"reports/T7_{k}_verifier.json", last_verify)
        verify_results.append(last_verify.get("result", {}))
        recovered = bool(last_verify.get("result", {}).get("recovered"))
        bus.emit("VERIFIER", "REPAIRER", "VERIFY_RESULT",
                 {"round": k, "recovered": recovered}, round_=k)  # 双向：验证→修复
        if recovered:
            break

    # 阶段C：报告
    condensed = {
        "root_cause": root_cause, "recovered": recovered,
        "repair_actions": [{"action": a["decision"].get("action"),
                            "target": a["decision"].get("target"),
                            "exec_rc": a["exec"].get("rc"),
                            "refused": a["exec"].get("refused")} for a in repair_actions],
        "verify_results": verify_results,
        "mode": args.mode, "host": collection.get("host"),
        "task_durations": {t["task_id"]: t["dur_s"] for t in timeline},
    }
    out_p = sched.run([Task("T8", "reporter",
                            lambda _u: json.dumps(condensed, ensure_ascii=False))], load_agent)
    timeline.extend(out_p["timeline"])
    ws.write_text("report.md", out_p["results"]["T8"].get("result", ""))

    wall = round(time.time() - t_start, 2)
    gold = None
    if args.gold:
        gf = REPO / "testbed" / "faults" / f"{args.gold}.json"
        gold = json.loads(gf.read_text(encoding="utf-8"))["gold"]
        comp = (root_cause.get("component") or "").lower()
        gold_comp = gold["component"].lower()
        gold_stem = gold_comp.split(".")[0]  # 容忍模型给出完整命令行而非短名
        gold = {**gold,
                "category_ok": root_cause.get("category") == gold["category"],
                "component_ok": bool(comp) and (gold_comp in comp or gold_stem in comp)}

    summary = {
        "mode": args.mode, "pipeline": "v2", "wall_s": wall,
        "verdict": root_cause, "gold": gold,
        "recovery_ok": recovered, "repair_rounds": len(repair_actions),
        "repair_actions": condensed["repair_actions"],
        "tasks": [{"id": t["task_id"], "agent": t["agent"], "dur_s": t["dur_s"],
                   "ok": t["ok"]} for t in sorted(timeline, key=lambda x: x["start"])],
        "messages": bus.count,
    }
    ws.write_json("summary.json", summary)
    ws.write_json("timeline.json", timeline)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
