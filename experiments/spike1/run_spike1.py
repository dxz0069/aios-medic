#!/usr/bin/env python3
"""Spike ①：7B 诊断单输出可靠性测试（M0 kill-switch 依据）。

对 20 条合成日志/指标样本调用 OpenAI 兼容端点（vLLM/ollama 均可），评测
LogAnalyst 风格提示词下的结构化输出质量：
  - parse_ok   : JSON 解析成功率（含 ≤2 次重试）
  - category   : 故障类目判定准确率
  - component  : 组件定位准确率（宽松匹配）
  - evidence   : 金标签证据召回率
判定口径（kill-switch）：总失败率 = 1 - min(parse_ok, category) > 30% 则回退备选场景。

用法:
  python run_spike1.py --base-url http://127.0.0.1:8091/v1 --model Qwen/Qwen2.5-7B-Instruct-AWQ
  python run_spike1.py --selftest          # 不调 LLM，验证脚本链路
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CATEGORIES = ["resource/memory", "resource/disk", "resource/cpu", "service/crash", "network/loss", "none"]

SYSTEM_PROMPT = (
    "你是 Medic 多智能体系统中的系统日志分析智能体。给定一段来自 Linux 受控环境的"
    "工具输出片段（dmesg/ps/sar/df/ping/tc/服务日志等），判断是否存在异常。"
    "仅输出一个 JSON 对象，不要输出任何其他文字或代码块标记，字段如下：\n"
    '{"category": "resource/memory|resource/disk|resource/cpu|service/crash|network/loss|none",\n'
    ' "component": "定位到的组件（进程名/目录/设备/服务名），无异常为空字符串",\n'
    ' "confidence": 0.0到1.0的数字,\n'
    ' "anomalies": ["异常现象描述"],\n'
    ' "evidence": ["引用原文的关键行"],\n'
    ' "need_more": "证据不足时指出需补充采集的源(log/metric/proc/net)，否则为空字符串"}'
)


def load_samples(samples_dir: Path):
    samples = []
    for f in sorted(samples_dir.glob("samples_*.json")):
        samples.extend(json.loads(f.read_text(encoding="utf-8"))["samples"])
    return samples


def chat(base_url: str, model: str, messages: list, temperature: float, timeout: int) -> str:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "messages": messages,
                         "temperature": temperature, "max_tokens": 512}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def extract_json(text: str):
    """从模型输出中提取 JSON：先整体 parse，再剥离代码围栏，再抓第一个 {...}。"""
    text = text.strip()
    for candidate in (text,
                      re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip(),
                      re.search(r"\{.*\}", text, re.S).group(0) if re.search(r"\{.*\}", text, re.S) else ""):
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def call_model(base_url, model, sample, temperature, timeout):
    """带 ≤2 次重试的调用；重试时附加纠错指令。返回 (obj, raw_first, parse_ok)。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"工具输出片段（来源: {sample['source']}）:\n\n{sample['snippet']}"}]
    raw_first = ""
    for attempt in range(3):
        raw = chat(base_url, model, messages, temperature, timeout)
        if attempt == 0:
            raw_first = raw
        obj = extract_json(raw)
        if obj is not None:
            return obj, raw_first, True
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": "上一个输出不是合法 JSON。仅重新输出 JSON 对象本身。"})
    return None, raw_first, False


def component_match(pred: str, gold: str) -> bool:
    p, g = (pred or "").lower().strip(), (gold or "").lower().strip()
    return bool(p) and bool(g) and (g in p or p in g)


def evidence_recall(pred_text: str, gold_evidence: list) -> float:
    if not gold_evidence:
        return 1.0
    hay = (pred_text or "").lower()
    hit = sum(1 for ev in gold_evidence if ev.lower() in hay or all(
        w.lower() in hay for w in ev.split() if len(w) > 2))
    return hit / len(gold_evidence)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8091/v1")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    ap.add_argument("--samples", default=str(Path(__file__).parent / "samples"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "results"))
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--selftest", action="store_true", help="不调用 LLM，用金标签伪造响应验证链路")
    args = ap.parse_args()

    samples = load_samples(Path(args.samples))
    rows = []
    t0 = time.time()
    for s in samples:
        gold = s["gold"]
        if args.selftest:
            obj = {"category": gold["category"], "component": gold["component"],
                   "confidence": 0.9, "anomalies": [], "evidence": gold["evidence"], "need_more": ""}
            raw_first, parse_ok = json.dumps(obj, ensure_ascii=False), True
        else:
            obj, raw_first, parse_ok = call_model(args.base_url, args.model, s,
                                                  args.temperature, args.timeout)
        pred_text = json.dumps(obj, ensure_ascii=False) if obj else raw_first
        row = {
            "id": s["id"], "source": s["source"], "parse_ok": parse_ok,
            "category_ok": bool(obj and obj.get("category") == gold["category"]),
            "component_ok": bool(obj and component_match(obj.get("component", ""), gold["component"])),
            "evidence_recall": round(evidence_recall(pred_text, gold["evidence"]), 2),
            "pred_category": (obj or {}).get("category", ""),
            "gold_category": gold["category"],
            "raw_first": raw_first[:400],
        }
        rows.append(row)
        print(f"[{row['id']}] parse={row['parse_ok']} cat={row['category_ok']} "
              f"comp={row['component_ok']} evid={row['evidence_recall']}")

    n = len(rows)
    agg = {
        "n": n,
        "parse_ok": round(sum(r["parse_ok"] for r in rows) / n, 3),
        "category_acc": round(sum(r["category_ok"] for r in rows) / n, 3),
        "component_acc": round(sum(r["component_ok"] for r in rows) / n, 3),
        "evidence_recall_avg": round(sum(r["evidence_recall"] for r in rows) / n, 3),
        "model": "selftest" if args.selftest else args.model,
        "base_url": "selftest" if args.selftest else args.base_url,
        "elapsed_s": round(time.time() - t0, 1),
    }
    failure = round(1 - min(agg["parse_ok"], agg["category_acc"]), 3)
    agg["kill_switch_failure_rate"] = failure
    agg["verdict"] = "PASS（≤30%，可继续 Medic）" if failure <= 0.30 else "FAIL（>30%，触发回退 DevForge）"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "spike1_results.json").write_text(
        json.dumps({"aggregate": agg, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Spike ① 结果", "",
          f"- 模型: `{agg['model']}`  端点: `{agg['base_url']}`  样本数: {n}  耗时: {agg['elapsed_s']}s", "",
          "| 指标 | 值 |", "|---|---|",
          f"| JSON 解析成功率 | {agg['parse_ok']} |",
          f"| 类目准确率 | {agg['category_acc']} |",
          f"| 组件定位准确率 | {agg['component_acc']} |",
          f"| 证据召回率 | {agg['evidence_recall_avg']} |",
          f"| **kill-switch 失败率** | **{failure}** |",
          f"| 结论 | {agg['verdict']} |", "",
          "| id | 来源 | parse | 类目 | 组件 | 证据召回 |", "|---|---|---|---|---|---|"]
    md += [f"| {r['id']} | {r['source']} | {r['parse_ok']} | {r['category_ok']} | "
           f"{r['component_ok']} | {r['evidence_recall']} |" for r in rows]
    (out_dir / "spike1_report.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(agg, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
