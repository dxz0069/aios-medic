"""F10 日志风暴：高频向 /var/log/medic/flood.log 写入告警样式行（~1.3MB/s）。

证据链：flood.log 体积（采集器 flood_log_mb > 20 触发告警）+ log 源尾部刷屏行。
修复联动：actions.py 对 log_fog 目标 kill 后清空 flood.log（否则告警位不复位）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f10"

_FLOOD = r"""
import os, time
with open("/var/log/medic/flood.log", "a") as f:
    while True:
        line = time.strftime("%Y-%m-%dT%H:%M:%S+00:00") + " log_flood pid=" + str(os.getpid()) + \
               " WARN connection pool exhausted, retrying upstream (attempt 1/3)\n"
        f.write(line * 500)
        f.flush()
        time.sleep(0.05)
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        import os
        try:
            mb = round(os.path.getsize("/var/log/medic/flood.log") / 2**20, 1)
        except OSError:
            mb = 0.0
        print(f"{NAME}: flood pid={pid} alive={_util.is_alive(pid)} flood_log_mb={mb}")
        return 0
    if action == "clear":
        _util.kill_pid(pid)
        try:
            open("/var/log/medic/flood.log", "w").close()
        except OSError:
            pass
        print(f"{NAME}: cleared (process killed + log truncated)")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        new_pid = _util.spawn_detached([sys.executable, "-c", _FLOOD])
        _util.write_pid(NAME, new_pid)
        print(f"{NAME}: injected log_flood pid={new_pid} (~1.3MB/s)")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
