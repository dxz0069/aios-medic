#!/usr/bin/env python3
"""Medic 故障注入统一 CLI（在沙箱容器内运行）。

用法:
  inject.py <F01|F02|...> --action inject|clear|status
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

# 故障注册表：id -> 实现模块（相对本文件）
REGISTRY = {
    "F01": "mem_leak",
    "F02": "disk_fill",
    "F03": "cpu_starve",
    "F04": "svc_crash",
    "F05": "net_loss",
}

FAULTS_DIR = Path(__file__).parent / "faults"


def case_meta(fid: str) -> dict:
    f = FAULTS_DIR / f"{fid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fault", choices=sorted(REGISTRY))
    ap.add_argument("--action", default="inject", choices=["inject", "clear", "status"])
    ap.add_argument("--meta", action="store_true", help="打印用例金标签元数据")
    args = ap.parse_args()

    if args.meta:
        print(json.dumps(case_meta(args.fault), ensure_ascii=False, indent=2))
        return 0

    mod = importlib.import_module(f"faults_impl.{REGISTRY[args.fault]}")
    return mod.run(args.action)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main())
