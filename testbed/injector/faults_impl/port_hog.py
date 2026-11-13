"""F18 端口占用冲突：抢占玩具服务的 8080 端口，supervisor 重启的服务无法绑定。

注入顺序：先停服务释放端口 → 立刻抢占（赶在 supervisor 1 秒重启之前）→
supervisor 反复重启失败（exited code=1）形成冲突循环。
证据链：ss -tlnp 显示 8080 被 port_hog 持有 + service.log 重启失败循环。
修复：kill port_hog → supervisor 下一次重启成功绑定 → 自愈。
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _util

NAME = "f18"

_HOG = r"""
# port_hog  (自标识：供修复执行器 pkill -f 匹配)
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 8080))
s.listen(5)
while True:
    time.sleep(3600)
"""


def run(action: str) -> int:
    pid = _util.read_pid(NAME)
    if action == "status":
        held = "8080" in subprocess.run(["ss", "-tlnp"], capture_output=True, text=True).stdout
        print(f"{NAME}: hog pid={pid} alive={_util.is_alive(pid)} port8080_listening={held}")
        return 0
    if action == "clear":
        killed = _util.kill_pid(pid)
        time.sleep(3)  # supervisor 下一轮重启即恢复
        print(f"{NAME}: clear killed={killed} (service self-heals via supervisor)")
        return 0
    if action == "inject":
        if _util.is_alive(pid):
            print(f"{NAME}: already injected (pid={pid})")
            return 0
        subprocess.run(["pkill", "-f", "service/service.py"])  # 释放端口
        time.sleep(0.3)
        new_pid = _util.spawn_detached([sys.executable, "-c", _HOG])
        _util.write_pid(NAME, new_pid)
        print(f"{NAME}: injected port_hog pid={new_pid} (bind 8080)")
        return 0
    print(f"unknown action: {action}")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else "status"))
