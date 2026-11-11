#!/usr/bin/env python3
"""汇总 M1 夜间构建结果：按故障×模式统计墙钟时间、正确性、提速百分比。

输入：--ws 目录（其下 <Fxx>/r<N>/{serial,concurrent}-*/summary.json）
输出：<ws>/night_summary.{json,md}
"""
import argparse
import glob
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    args = ap.parse_args()
    ws = Path(args.ws)

    faults: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ws / "F*" / "r*" / "*-*/summary.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        parts = Path(f).parts
        fault = parts[-4] if parts[-2].split("-")[0] in ("serial", "concurrent") else "?"
        # 路径形如 ws/F03/r1/serial-XXXX/summary.json
        fault = Path(f).parent.parent.parent.name
        rnd = Path(f).parent.parent.name
        faults.setdefault(fault, {}).setdefault(d["mode"], []).append(
            {"round": rnd, "wall_s": d["wall_s"],
             "category_ok": (d.get("gold") or {}).get("category_ok"),
             "component_ok": (d.get("gold") or {}).get("component_ok"),
             "recovery_ok": d.get("recovery_ok"),
             "repair_rounds": d.get("repair_rounds"),
             "verdict_cat": (d.get("verdict") or {}).get("category"),
             "verdict_comp": (d.get("verdict") or {}).get("component"),
             "confidence": (d.get("verdict") or {}).get("confidence")})

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 2) if xs else None

    report = {"faults": {}}
    lines = ["# M1 夜间构建汇总", "",
             "| 故障 | 串行均值(s) | 并发均值(s) | 提速% | 类目正确 | 组件正确 | 恢复成功 | 结论(并发末轮) |",
             "|---|---|---|---|---|---|---|---|"]
    for fault, modes in sorted(faults.items()):
        s = [r["wall_s"] for r in modes.get("serial", [])]
        c = [r["wall_s"] for r in modes.get("concurrent", [])]
        all_runs = [r for m in ("serial", "concurrent") for r in modes.get(m, [])]
        cat_ok = [r["category_ok"] for r in all_runs]
        comp_ok = [r["component_ok"] for r in all_runs]
        rec = [r.get("recovery_ok") for r in all_runs if r.get("recovery_ok") is not None]
        speedup = round((mean(s) - mean(c)) / mean(s) * 100, 1) if s and c and mean(s) else None
        last = modes.get("concurrent", [{}])[-1]
        report["faults"][fault] = {
            "serial_wall_mean_s": mean(s), "concurrent_wall_mean_s": mean(c),
            "speedup_pct": speedup, "rounds": len(s), "rounds_conc": len(c),
            "category_ok_rate": f"{sum(1 for x in cat_ok if x)}/{len(cat_ok)}",
            "component_ok_rate": f"{sum(1 for x in comp_ok if x)}/{len(comp_ok)}",
            "recovery_ok_rate": (f"{sum(1 for x in rec if x)}/{len(rec)}" if rec else "n/a"),
            "last_verdict": {k: last.get(k) for k in ("verdict_cat", "verdict_comp", "confidence")}}
        lines.append(f"| {fault} | {mean(s)} | {mean(c)} | {speedup} "
                     f"| {report['faults'][fault]['category_ok_rate']} "
                     f"| {report['faults'][fault]['component_ok_rate']} "
                     f"| {report['faults'][fault]['recovery_ok_rate']} "
                     f"| {last.get('verdict_cat')} / {last.get('verdict_comp')} |")

    ws.joinpath("night_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ws.joinpath("night_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
