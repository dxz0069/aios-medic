"""注入器公共工具：PID 文件管理与后台进程存活检查。"""
import os
import signal
import subprocess
from pathlib import Path

RUN_DIR = Path("/run/medic")


def write_pid(name: str, pid: int) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / f"{name}.pid").write_text(str(pid))


def read_pid(name: str):
    f = RUN_DIR / f"{name}.pid"
    if not f.exists():
        return None
    try:
        return int(f.read_text().strip())
    except ValueError:
        return None


def is_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def kill_pid(pid) -> bool:
    if not is_alive(pid):
        return False
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except OSError:
        return False


def spawn_detached(argv) -> int:
    """以独立会话启动子进程（父进程退出后仍存活），返回 pid。"""
    proc = subprocess.Popen(argv, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.pid
