#!/usr/bin/env python3
"""Medic 采集器：从受控环境采集四源快照 + 告警评估（容器内运行，纯标准库）。

输出 JSON：{"ts", "host", "alert": {...阈值判定...}, "sources": {"log","metric","proc","net"}}
供分析智能体消费；告警部分供 Commander 生成诊断计划。
"""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path


def cpu_count_effective() -> int:
    """有效 CPU 数：容器内 os.cpu_count() 返回宿主核数（128），
    sched_getaffinity 反映 cgroup/亲和性实际配额（16，与 nproc 一致）。"""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def sh(cmd: str, limit: int = 3000) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return ((r.stdout or "") + (r.stderr or ""))[:limit]
    except Exception as e:  # noqa: BLE001 - 采集必须兜错
        return f"[collect-error] {e}"


def tail_file(path: str, n: int = 2000) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode(errors="replace")
    except OSError:
        return ""


def collect() -> dict:
    meminfo = Path("/proc/meminfo").read_text()
    total = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1))
    avail = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1))
    loadavg_parts = Path("/proc/loadavg").read_text().split()
    load1 = float(loadavg_parts[0])
    runnable = int(loadavg_parts[3].split("/")[0])
    ncpu = cpu_count_effective()

    df_out = sh("df -h / /var/scratch 2>/dev/null")
    disk_pct = 0
    m = re.search(r"(\d+)%\s+/var/scratch", df_out) or re.search(r"(\d+)%\s+/\n", df_out + "\n")
    if m:
        disk_pct = int(m.group(1))

    gw = sh("ip route show default 2>/dev/null | head -1 | awk '{print $3}'").strip()
    ping_out = sh(f"ping -c 3 -W 1 {gw or '127.0.0.1'} 2>&1") if gw else "[no-default-route]"
    loss = 0.0
    for line in ping_out.splitlines():
        if "packet loss" in line:
            try:
                loss = float(line.split(",")[2].strip().split("%")[0])
            except (IndexError, ValueError):
                pass

    service_log = tail_file("/var/log/medic/service.log")
    dmesg_out = sh("dmesg 2>&1 | head -15")
    leaky_log = tail_file("/var/log/medic/leaky.log", 800)

    log_parts = []
    if service_log:
        log_parts.append("== service.log (tail) ==\n" + service_log)
    if leaky_log:
        log_parts.append("== leaky.log (tail) ==\n" + leaky_log)
    flood_tail = tail_file("/var/log/medic/flood.log", 800)
    if flood_tail:
        log_parts.append("== flood.log (tail) ==\n" + flood_tail)
    if dmesg_out and "collect-error" not in dmesg_out:
        log_parts.append("== dmesg (head) ==\n" + dmesg_out)
    if not log_parts:
        log_parts.append("[no-log-source]")

    ss_ports = sh("ss -tlnp 2>/dev/null | head -8")
    sources = {
        "log": "\n".join(log_parts),
        "metric": (f"== /proc/loadavg ==\n{' '.join(loadavg_parts)}\n"
                   f"ncpu={ncpu}\n\n== /proc/meminfo (摘要) ==\n"
                   f"MemTotal={total}kB MemAvailable={avail}kB "
                   f"used_pct={round((total - avail) / total * 100, 1)}%\n\n== df ==\n{df_out}"),
        "proc": sh("ps aux --sort=-rss 2>/dev/null | head -12")
        + "\n\n== 僵尸进程统计 ==\n数量: " + sh("ps aux 2>/dev/null | grep -c defunct").strip()
        + "\n样例(前5行):\n" + sh("ps aux 2>/dev/null | grep defunct | head -5")
        + "\n僵尸父进程:\n" + sh("ps -o pid,stat,cmd -p $(ps -o ppid= -C python3 2>/dev/null | sort -u | head -3 | tr '\\n' ',' | sed 's/,$//') 2>/dev/null | head -5"),
        "net": (f"== ping {gw} ==\n{ping_out}\n\n== tc qdisc ==\n"
                f"{sh('tc qdisc show 2>&1 | head -6')}\n\n== ss -s ==\n{sh('ss -s 2>&1')}"
                f"\n\n== 监听端口(ss -tlnp) ==\n{ss_ports}"),
    }

    service_ok = False
    try:
        from http.client import HTTPConnection
        conn = HTTPConnection("127.0.0.1", 8080, timeout=2)
        conn.request("GET", "/health")
        service_ok = conn.getresponse().status == 200
        conn.close()
    except OSError:
        pass

    # 新增告警位：僵尸进程堆积 / 日志风暴 / 端口被占（F06/F10/F18）
    zombies_out = sh("ps aux 2>/dev/null | grep -c defunct").strip()
    try:
        zombies = int(zombies_out.splitlines()[-1]) if zombies_out else 0
    except (ValueError, IndexError):
        zombies = 0
    flood_mb = 0.0
    try:
        flood_mb = round(os.path.getsize("/var/log/medic/flood.log") / 2**20, 1)
    except OSError:
        pass
    port_hogged = (not service_ok) and (":8080" in ss_ports) and ("service.py" not in ss_ports)

    alert = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": os.uname().nodename,
        "cpu": runnable > ncpu,
        "memory": avail < total * 0.10,
        "disk": disk_pct > 90,
        "network": loss > 10,
        "service": not service_ok and not port_hogged,
        "process": zombies > 50,
        "logs": flood_mb > 20,
        "port": port_hogged,
        "values": {"load1": load1, "runnable": runnable, "ncpu": ncpu,
                   "zombies": zombies, "flood_log_mb": flood_mb,
                   "port_hogged": port_hogged,
                   "mem_avail_pct": round(avail / total * 100, 1),
                   "disk_pct": disk_pct, "ping_loss_pct": loss,
                   "service_ok": service_ok},
    }
    return {"ts": alert["ts"], "host": alert["host"], "alert": alert, "sources": sources}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    args = ap.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    data = collect()
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": args.out, "alert": data["alert"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
