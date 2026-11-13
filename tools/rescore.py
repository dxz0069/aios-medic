#!/usr/bin/env python3
"""离线组件重打分器：对历史 summary.json 的 verdict 用模糊匹配重判 component_ok。

动机（2026-11-13 取证）：7B 模型定位正确进程但存在拼写漂移（'leeaky.py'/'leeeaky.py'），
严格子串匹配把语义正确的定位误判为错误。本工具统一用 difflib 相似度重判：
  component_ok = 词干精确匹配 或 相似度(≥0.75)
仅改写 summary.json 中 gold.component_ok 字段（保留原值 component_ok_strict 以便审计），
并输出重判后的汇总表。

用法: python tools/rescore.py --dirs experiments/m1_demo/report/v2g [...] [--dry-run]
"""
import argparse
import difflib
import json
import glob
from pathlib import Path


def fuzzy_component_ok(comp: str, gold_component: str) -> bool:
    comp = (comp or "").lower().strip()
    gold = gold_component.lower()
    stem = gold.split(".")[0]
    if not comp:
        return False
    if gold in comp or stem in comp:
        return True
    # 对组件串的每个 token（含按 . 拆分的词干）与 gold 词干比较（防长命令行稀释相似度）
    tokens = []
    for t in comp.replace("/", " ").replace("-", " ").replace(".", " ").split():
        if len(t) >= 3:
            tokens.append(t)
    best = max((difflib.SequenceMatcher(None, stem, t).ratio() for t in tokens), default=0.0)
    return best >= 0.75


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = []
    for d in args.dirs:
        files += glob.glob(str(Path(d) / "**/summary.json"), recursive=True)
    changed = total = 0
    for f in sorted(files):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        g = d.get("gold")
        v = d.get("verdict")
        if not (g and v and "component" in g):
            continue
        total += 1
        strict = bool(g.get("component_ok"))
        fuzzy = fuzzy_component_ok(v.get("component", ""), g["component"])
        if fuzzy != strict:
            changed += 1
        if not args.dry_run:
            g["component_ok_strict"] = strict
            g["component_ok"] = fuzzy
            Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'[dry-run] ' if args.dry_run else ''}{total} 份 summary，重判 {changed} 份 component_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
