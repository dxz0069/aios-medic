FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip procps sysstat iproute2 iputils-ping curl util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Medic 实验床组件（build context = testbed/）
COPY sandbox/service/ /opt/medic/service/
COPY injector/       /opt/medic/injector/
COPY probes/         /opt/medic/probes/
COPY signatures/     /opt/medic/signatures/
COPY faults/         /opt/medic/faults/

RUN mkdir -p /var/log/medic /run/medic /var/scratch

EXPOSE 8080

# supervisor 常驻：拉起并守护玩具 HTTP 服务，崩溃自动重启（模拟 systemd 行为）
CMD ["python3", "/opt/medic/service/supervisor.py"]
