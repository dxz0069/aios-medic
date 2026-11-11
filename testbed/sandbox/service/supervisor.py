"""玩具服务的 supervisor：拉起 service.py，崩溃后自动重启（模拟 systemd 行为）。

日志写入 /var/log/medic/service.log，行格式模仿 syslog，供 LogAnalyst 采集：
  2026-11-11T12:00:00+00:00 medic-sandbox toy-critical-service[1234]: service started (pid=1234)
"""
import os
import signal
import subprocess
import sys
import time

SERVICE = "/opt/medic/service/service.py"
LOG = "/var/log/medic/service.log"
HOST = "medic-sandbox"


def log(pid: int, msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{ts} {HOST} toy-critical-service[{pid}]: {msg}\n")


def main() -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    stopping = {"flag": False}

    def on_term(_sig, _frm):
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, on_term)

    while not stopping["flag"]:
        proc = subprocess.Popen([sys.executable, SERVICE])
        log(proc.pid, "service started")
        rc = proc.wait()
        if stopping["flag"] and rc in (0, -signal.SIGTERM):
            log(proc.pid, "supervisor stopping")
            break
        log(proc.pid, f"main process exited, code={rc}; status=failed/running-restart")
        time.sleep(1)


if __name__ == "__main__":
    main()
