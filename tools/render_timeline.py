#!/usr/bin/env python3
"""执行时间线可视化：timeline.json + messages.jsonl → 自包含 HTML 甘特图。

对比串行/并发两种调度模式同一流水线的任务时间线（性能对比实验的核心展示）。

用法:
  python tools/render_timeline.py --runs <dir1> <dir2> [...] --out timeline.html
  每个 run 目录需含 timeline.json（与 summary.json 同级，由 run_pipeline*.py 产出）
"""
import argparse
import html
import json
from pathlib import Path

AGENT_COLORS = {
    "commander": "#8e44ad", "log_analyst": "#2980b9", "metric_analyst": "#16a085",
    "proc_analyst": "#27ae60", "net_analyst": "#f39c12", "diagnostician": "#c0392b",
    "repairer": "#d35400", "verifier": "#7f8c8d", "reporter": "#2c3e50",
}


def load_run(d: Path) -> dict:
    tl = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    summary = {}
    if (d / "summary.json").exists():
        summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    n_msgs = 0
    if (d / "messages.jsonl").exists():
        n_msgs = sum(1 for _ in (d / "messages.jsonl").open(encoding="utf-8"))
    t0 = min(t["start"] for t in tl)
    for t in tl:
        t["rel"] = round(t["start"] - t0, 2)
    return {"name": d.name, "dir": str(d), "timeline": sorted(tl, key=lambda x: x["rel"]),
            "wall": summary.get("wall_s"), "mode": summary.get("mode"),
            "recovery": summary.get("recovery_ok"), "n_msgs": n_msgs, "t_end": max(
                (t["rel"] + t["dur_s"]) for t in tl)}


def svg_run(run: dict, width: int = 900, row_h: int = 26, pad: int = 150) -> str:
    dur_total = max(run["t_end"], 1)
    scale = (width - pad - 20) / dur_total
    rows, out = [], []
    for i, t in enumerate(run["timeline"]):
        y = i * row_h + 30
        x = pad + t["rel"] * scale
        w = max(t["dur_s"] * scale, 2)
        color = AGENT_COLORS.get(t["agent"], "#34495e")
        label = f"{html.escape(t['task_id'])} · {html.escape(t['agent'])} ({t['dur_s']}s)"
        rows.append(
            f'<text x="{pad - 8}" y="{y + 14}" text-anchor="end" font-size="12" fill="#333">{label}</text>'
            f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{row_h - 8}" rx="3" fill="{color}" fill-opacity="0.85">'
            f'<title>{html.escape(t["task_id"])} {html.escape(t["agent"])} rel={t["rel"]}s dur={t["dur_s"]}s</title></rect>')
    h = len(run["timeline"]) * row_h + 40
    return (f'<svg width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="{h}" fill="#fdfdfd" stroke="#ddd"/>'
            + "".join(rows) + "</svg>")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Medic 流水线时间线对比")
    args = ap.parse_args()

    runs = [load_run(Path(r)) for r in args.runs]
    secs = []
    for run in runs:
        meta = (f"wall={run['wall']}s · 消息数={run['n_msgs']}"
                + (f" · 恢复={'是' if run['recovery'] else '否'}" if run["recovery"] is not None else ""))
        secs.append(f"<h2>{html.escape(run['name'])}</h2><p>{meta}</p>{svg_run(run)}")

    doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(args.title)}</title></head>"
           f"<body style='font-family:sans-serif;margin:20px'><h1>{html.escape(args.title)}</h1>"
           + "".join(secs) + "</body></html>")
    Path(args.out).write_text(doc, encoding="utf-8")
    print(f"written: {args.out} ({len(runs)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
