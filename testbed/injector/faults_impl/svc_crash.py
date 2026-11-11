"""F04 关键服务崩溃循环：反复 kill -9 玩具服务，supervisor 不断重启 → 崩溃循环。

证据链：service.log 的 restart 循环行（exited code=-9 / status=failed/running-restart）
+ 健康探针服务不可达 + curl 连接拒绝。
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f04"

_CRASHER = r"""
import os, signal, subprocess, time
while True:
    out = subprocess.run(["pgrep", "-f", "service/service.py"], capture_output=True, text=True)
    for pid in out.stdout.split():
        try:
            os.kill(int(pid), signal.SIGKILL)
        except OSError:
            pass
    time.sleep(2)
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        print(f"{NAME}: crasher pid={pid} alive={_util.is_alive(pid)}")
        return 0
    if action == "clear":
        killed = _util.kill_pid(pid)
        print(f"{NAME}: clear killed={killed} (service will stabilise via supervisor)")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        new_pid = _util.spawn_detached([sys.executable, "-c", _CRASHER])
        _util.write_pid(NAME, new_pid)
        print(f"{NAME}: injected crasher pid={new_pid} (kill -9 every 2s)")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
