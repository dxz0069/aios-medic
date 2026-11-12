"""F01 内存泄漏进程：后台进程持续增大 RSS，直至被容器内存上限触发 OOM 或被清除。

证据链：/var/log/medic/leaky.log（自身 RSS 记录）+ ps RSS 增长 + sar 内存水位。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f01"
LOG = Path("/var/log/medic/leaky.log")

_LEAKY = r"""
import os, time
buf = []
with open("/var/log/medic/leaky.log", "a") as f:
    while True:
        buf.append(bytearray(128 * 1024 * 1024))  # 每秒 +128MB（低速率：减少诊断期间对系统的连带压力）
        rss = int(next(l for l in open("/proc/self/status") if l.startswith("VmRSS")).split()[1])
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())} leaky.py pid={os.getpid()} VmRSS={rss}kB\n")
        f.flush()
        time.sleep(1)
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        print(f"{NAME}: pid={pid} alive={_util.is_alive(pid)}")
        return 0
    if action == "clear":
        killed = _util.kill_pid(pid)
        print(f"{NAME}: clear killed={killed}")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        LOG.parent.mkdir(parents=True, exist_ok=True)
        new_pid = _util.spawn_detached([sys.executable, "-c", _LEAKY])
        _util.write_pid(NAME, new_pid)
        print(f"{NAME}: injected pid={new_pid} (+128MB/s)")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
