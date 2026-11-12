#!/usr/bin/env python3
"""Medic 健康探针（容器内运行）：输出 JSON 健康快照，供 Verifier 判定与实验采集。

探针项: cpu(负载) / memory(可用) / disk(scratch 水位) / service(HTTP 健康) / network(网关 ping)
"""
import json
import os
import subprocess
import time
from http.client import HTTPConnection


def probe_cpu() -> dict:
    load1, load5, _load15, runnable_total, _lastpid = open("/proc/loadavg").read().split()
    runnable = int(runnable_total.split("/")[0])
    try:  # 容器内 affinity 才是有效核数（同 nproc）
        ncpu = max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        ncpu = os.cpu_count() or 1
    return {"value": {"load1": float(load1), "runnable": runnable, "ncpu": ncpu},
            "ok": runnable <= ncpu}


def probe_memory() -> dict:
    info = {l.split(":")[0]: l.split()[1] for l in open("/proc/meminfo") if ":" in l}
    total, avail = int(info["MemTotal"]), int(info["MemAvailable"])
    return {"value": {"total_kb": total, "available_kb": avail,
                      "used_pct": round((total - avail) / total * 100, 1)},
            "ok": avail > total * 0.10}


def probe_disk() -> dict:
    st = os.statvfs("/var/scratch")
    total, free = st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
    used_pct = round((total - free) / total * 100, 1) if total else -1.0
    return {"value": {"total_mb": total >> 20, "free_mb": free >> 20, "used_pct": used_pct},
            "ok": used_pct < 90}


def probe_service() -> dict:
    try:
        conn = HTTPConnection("127.0.0.1", 8080, timeout=2)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        conn.close()
        return {"value": {"http_status": resp.status, "service_status": body.get("status")},
                "ok": resp.status == 200}
    except OSError as e:
        return {"value": {"error": str(e)}, "ok": False}


def probe_network() -> dict:
    route = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
    gw = route.stdout.split()[2] if route.returncode == 0 and len(route.stdout.split()) > 2 else "127.0.0.1"
    ping = subprocess.run(["ping", "-c", "3", "-W", "1", gw], capture_output=True, text=True)
    loss_pct, rtt_avg = 100.0, None
    for line in ping.stdout.splitlines():
        if "packet loss" in line:
            loss_pct = float(line.split(",")[2].strip().split("%")[0])
        if line.startswith("rtt/") or " = " in line and "min/avg/max" in line:
            try:
                rtt_avg = float(line.split("=")[1].split("/")[1])
            except (IndexError, ValueError):
                pass
    return {"value": {"gateway": gw, "loss_pct": loss_pct, "rtt_avg_ms": rtt_avg},
            "ok": loss_pct < 10}


PROBES = {"cpu": probe_cpu, "memory": probe_memory, "disk": probe_disk,
          "service": probe_service, "network": probe_network}


def main() -> int:
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
           "probes": {name: fn() for name, fn in PROBES.items()}}
    out["ok"] = all(p["ok"] for p in out["probes"].values())
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
