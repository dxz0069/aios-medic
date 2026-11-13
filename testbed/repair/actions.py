#!/usr/bin/env python3
"""确定性修复执行器（白名单动作，容器内由流水线经 subprocess 调用）。

用法: python3 testbed/repair/actions.py --action <A> --target <T>
输出: JSON {"action","target","rc","detail","ts","refused"}

安全边界：
- kill_by_pattern 的 target 必须命中 APPROVED_PATTERNS（防 LLM 越权杀进程）；
- 全部动作只影响受控实验床内的目标，白名单外动作一律拒绻执行。
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

APPROVED_PATTERNS = {
    "leaky",                        # F01 内存泄漏进程（cmdline 含 leaky）
    "import multiprocessing as mp",  # F03 忙循环进程组特征
    "signal.SIGKILL",               # F04 崩溃循环制造者特征
    "service/service.py",           # 玩具服务（配合 supervisor 重启）
    "zombie_maker",                 # F06 僵尸制造者（cmdline 含自标识注释）
    "log_flood",                    # F10 日志风暴进程
    "port_hog",                     # F18 端口占用进程
}
WHITELIST = ("kill_by_pattern", "tc_clear", "clear_scratch", "restart_service", "none")


def _run(cmd: list) -> dict:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return {"rc": r.returncode, "out": (r.stdout + r.stderr).strip()[:300]}


def execute(action: str, target: str = "") -> dict:
    res = {"action": action, "target": target, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "rc": 0, "detail": "", "refused": False}

    if action not in WHITELIST:
        res.update(refused=True, rc=2, detail=f"动作不在白名单: {action}")
        return res

    if action == "kill_by_pattern":
        if target not in APPROVED_PATTERNS:
            res.update(refused=True, rc=3,
                       detail=f"进程特征未获批准: {target!r}（防越权）")
            return res
        cnt = _run(["pgrep", "-fc", target])
        killed = _run(["pkill", "-f", target])
        detail = f"matched={cnt['out']} pkill={killed['out'] or 'ok'}"
        if target == "log_flood":  # 日志风暴：kill 后必须清文件，否则体积告警位不复位
            try:
                Path("/var/log/medic/flood.log").write_text("", encoding="utf-8")
                detail += " flood.log truncated"
            except OSError:
                pass
        res.update(rc=killed["rc"], detail=detail)

    elif action == "tc_clear":
        r = _run(["tc", "qdisc", "del", "dev", target or "eth0", "root"])
        res.update(rc=r["rc"], detail=r["out"] or "qdisc removed")

    elif action == "clear_scratch":
        d = Path(target or "/var/scratch")
        removed = 0
        for f in d.glob("fill.chunk.*"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        res.update(detail=f"removed {removed} chunks")

    elif action == "restart_service":
        _run(["pkill", "-f", "service/service.py"])  # supervisor 会自动拉起
        time.sleep(2)
        r = _run(["curl", "-s", "--max-time", "3", "http://127.0.0.1:8080/health"])
        res.update(rc=r["rc"], detail=f"health={r['out'][:80]}")

    else:  # none
        res.update(detail="no-op")

    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True)
    ap.add_argument("--target", default="")
    args = ap.parse_args()
    print(json.dumps(execute(args.action, args.target), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
