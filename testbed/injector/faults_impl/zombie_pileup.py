"""F06 僵尸进程堆积：父进程持续产生立即退出的子进程且不 wait（不回收）。

证据链：ps 中大量 <defunct> 行 + 采集器 zombies 统计 > 50。
可修复性：SIGTERM 处理器统一 wait 回收全部僵尸后退出（pkill 默认 TERM）。
"""
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f06"
COUNT = 300

_ZOMBIE = r"""
# zombie_maker  (自标识：供修复执行器 pkill -f 匹配)
import os
import signal
import sys
import time


def _reap_and_exit(_sig, _frm):
    try:
        while True:
            os.waitpid(-1, os.WNOHANG)
    except ChildProcessError:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, _reap_and_exit)
for _ in range(300):
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    # 父进程不 wait —— 子进程成为僵尸
while True:
    time.sleep(3600)
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        import subprocess
        z = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout.count("defunct")
        print(f"{NAME}: maker pid={pid} alive={_util.is_alive(pid)} zombies={z}")
        return 0

    if action == "clear":
        # 必须 SIGTERM（父进程的处理器会 wait 回收全部僵尸）；SIGKILL 会让僵尸失去回收者
        sent = False
        if _util.is_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                sent = True
            except OSError:
                pass
            time.sleep(2)
        print(f"{NAME}: clear term_sent={sent}")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        new_pid = _util.spawn_detached([sys.executable, "-c", _ZOMBIE])
        _util.write_pid(NAME, new_pid)
        print(f"{NAME}: injected zombie_maker pid={new_pid} (target={COUNT} zombies)")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    import signal  # noqa: F401 - 顶层导入供 clear 分支使用
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
