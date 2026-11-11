#!/usr/bin/env python3
"""M1 演示流水线：采集快照 → Commander(计划) → 4 分析智能体 → Diagnostician(根因)。

用法（容器内，venv python）:
  python experiments/m1_demo/run_pipeline.py --collection ws/fault.json \
      --mode concurrent --out ws [--gold F03]

- 模式 serial/concurrent：同一套智能体与输入，仅调度不同（性能对比协议）
- 所有调度事件与消息经 MessageBus 落盘（messages.jsonl），时间线写 timeline.json
- --gold 对照 testbed/faults/<id>.json 的金标签给出正确性判定
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from middleware import MessageBus, Scheduler, Task, Workspace  # noqa: E402

ANALYST_SOURCE = {"log_analyst": "log", "metric_analyst": "metric",
                  "proc_analyst": "proc", "net_analyst": "net"}
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


def build_tasks(collection: dict) -> list:
    alert = collection.get("alert", {})
    tasks = [Task("T0", "commander",
                  lambda _up: json.dumps(alert, ensure_ascii=False),
                  meta={"stage": "plan"})]
    for i, (agent, src) in enumerate(ANALYST_SOURCE.items(), start=1):
        snippet = collection["sources"][src]
        tasks.append(Task(f"T{i}", agent,
                          lambda _up, s=src, sn=snippet: json.dumps(
                              {"source": s, "snippet": sn}, ensure_ascii=False),
                          deps=("T0",), meta={"stage": "analyze", "source": src}))

    def diag_input(up):
        diagnoses = {f"A{i}": up[f"T{i}"] for i in range(1, 5) if f"T{i}" in up}
        return json.dumps({"alert": alert, "diagnoses": diagnoses}, ensure_ascii=False)

    tasks.append(Task("T5", "diagnostician", diag_input,
                      deps=("T1", "T2", "T3", "T4"), meta={"stage": "aggregate"}))
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--mode", choices=["serial", "concurrent"], default="concurrent")
    ap.add_argument("--out", default=str(REPO / "experiments/m1_demo/ws"))
    ap.add_argument("--gold", default=None, help="故障 id（如 F03），对照 testbed/faults/")
    args = ap.parse_args()

    collection = json.loads(Path(args.collection).read_text(encoding="utf-8"))
    ws = Workspace(args.out, run_id=f"{args.mode}-{time.strftime('%m%d%H%M%S')}")
    ws.write_json("collection.json", collection)
    bus = MessageBus(ws)
    scheduler = Scheduler(bus, mode=args.mode, max_workers=4)

    t0 = time.time()
    out = scheduler.run(build_tasks(collection), load_agent)
    wall = round(time.time() - t0, 2)

    for tid, res in out["results"].items():
        ws.write_json(f"reports/{tid}_{res.get('agent_name', 'unknown')}.json", res)

    verdict = out["results"].get("T5", {}).get("result", {})
    gold = None
    if args.gold:
        gf = REPO / "testbed" / "faults" / f"{args.gold}.json"
        gold = json.loads(gf.read_text(encoding="utf-8"))["gold"]
        cat_ok = verdict.get("category") == gold["category"]
        comp = (verdict.get("component") or "").lower()
        gold_comp = gold["component"].lower()
        gold_stem = gold_comp.split(".")[0]  # 'leaky.py' → 'leaky'，容忍模型给出完整命令行
        comp_ok = bool(comp) and (gold_comp in comp or gold_stem in comp)
        gold = {**gold, "category_ok": cat_ok, "component_ok": comp_ok}

    summary = {
        "mode": args.mode, "wall_s": wall, "verdict": verdict, "gold": gold,
        "tasks": [{"id": t["task_id"], "agent": t["agent"], "dur_s": t["dur_s"],
                   "ok": t["ok"]} for t in out["timeline"]],
        "messages": bus.count,
    }
    ws.write_json("summary.json", summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
