"""F03 CPU 饱和/饥饿：启动 2×CPU 数量的忙循环进程，制造 run queue 堆积与负载飙升。

证据链：/proc/loadavg（r 队列、1min 负载）+ pidstat/ps %CPU +探针负载异常。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f03"

# 组长进程拉起 2×CPU 配额的忙循环子进程（同进程组，clear 时 pkill -g 整组清理）
# 注意：容器内 os.cpu_count()=宿主核数（128），必须用 cgroup 配额（16）计算，否则进程数爆炸
_BUSY = r"""
import multiprocessing as mp
def _burn():
    while True: pass
def _ncpu():
    try:
        parts = open("/sys/fs/cgroup/cpu.max").read().split()
        if parts[0] != "max":
            return max(1, int(int(parts[0]) / int(parts[1])))
    except (OSError, ValueError, IndexError):
        pass
    import os
    return os.cpu_count() or 1
if __name__ == "__main__":
    n = max(2, _ncpu() * 2)
    procs = [mp.Process(target=_burn) for _ in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        alive = _util.is_alive(pid)
        print(f"{NAME}: pid={pid} alive={alive} loadavg={open('/proc/loadavg').read().split()[:3]}")
        return 0
    if action == "clear":
        killed = _util.kill_pid(pid)
        # 忙循环为同组子进程：清理同会话残余
        os.system(f"pkill -g {pid} 2>/dev/null")
        print(f"{NAME}: clear killed={killed}")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        import os
        n = max(2, (os.cpu_count() or 2) * 2)
        pgid = _util.spawn_detached([sys.executable, "-c", _BUSY])
        _util.write_pid(NAME, pgid)
        print(f"{NAME}: injected pgid={pgid} busy_procs={n}")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
