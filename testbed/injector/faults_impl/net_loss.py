"""F05 网络丢包+延迟：tc netem 作用于容器 eth0（需 --cap-add NET_ADMIN）。

证据链：tc qdisc show 出现 netem + ping 丢包率/RTT + 应用超时报错。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

NAME = "f05"
DEV = "eth0"


def _tc(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["tc", *args], capture_output=True, text=True)


def run(action: str) -> int:
    if action == "status":
        out = _tc("qdisc", "show", "dev", DEV)
        active = "netem" in out.stdout
        print(f"{NAME}: netem_active={active}")
        if active:
            print(out.stdout.strip())
        return 0
    if action == "clear":
        out = _tc("qdisc", "del", "dev", DEV, "root")
        ok = out.returncode == 0
        print(f"{NAME}: clear ok={ok} {out.stderr.strip()}")
        return 0 if ok or "Cannot delete" in out.stderr else 1
    if action == "inject":
        out = _tc("qdisc", "add", "dev", DEV, "root", "netem", "loss", "30%", "delay", "100ms")
        if out.returncode != 0:
            print(f"{NAME}: inject FAILED: {out.stderr.strip()}")
            print("hint: 容器需要 --cap-add NET_ADMIN 启动（见 run_sandbox.sh）")
            return 1
        print(f"{NAME}: injected (loss 30%, delay 100ms on {DEV})")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
