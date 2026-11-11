# testbed/ — 受控实验床

一次性容器沙箱：向其注入已知故障（金标签 + 恢复判据预先定义），供 Medic 多智能体系统诊断与修复，并产出正确性/性能实验数据。

## 组成

```
sandbox/    Dockerfile 与玩具服务（受 supervisor 管理的 HTTP 服务，模拟关键服务）
faults/     故障目录：F01–F05 用例定义（含金标签），F06–F20 规划见 planned.md
injector/   统一注入 CLI + 各故障实现（纯 Python，无外部依赖）
probes/     健康探针（负载/内存/磁盘/服务/网络，输出 JSON）
signatures/ 确定性特征签名库（LLM 解析失败时的兜底与正确性下限）
run_sandbox.sh  一键启动沙箱（含 NET_ADMIN 权限与受限 tmpfs 挂载）
```

## 使用

```bash
# 构建与启动（build context 必须是 testbed/）
docker build -t medic-sandbox -f testbed/sandbox/Dockerfile testbed/
bash testbed/run_sandbox.sh            # 启动，容器名 medic-sandbox

# 注入/清除/查看故障
docker exec medic-sandbox python3 /opt/medic/injector/inject.py F01 --action inject
docker exec medic-sandbox python3 /opt/medic/injector/inject.py F01 --action status
docker exec medic-sandbox python3 /opt/medic/injector/inject.py F01 --action clear

# 健康探针（JSON 输出）
docker exec medic-sandbox python3 /opt/medic/probes/probes.py
```

## 安全边界

- 故障只影响一次性容器；`/var/scratch` 为受限 tmpfs（F02 磁盘写满只作用于它，不会写爆容器根文件系统）；
- F05 网络丢包需要容器以 `--cap-add NET_ADMIN` 启动（run_sandbox.sh 已包含）；
- 修复动作白名单由 Repairer 智能体遵守：仅 kill 指定 PID / 重启玩具服务 / 清理 /var/scratch / 删除 tc 规则。

## 采集源（供分析智能体使用，M1 接入）

| 源 | 命令 | 对应智能体 |
|---|---|---|
| 内核/系统日志 | `dmesg -T`、`/var/log/medic/service.log` | LogAnalyst |
| 指标 | `sar -r 1 3`、`/proc/loadavg`、`/proc/meminfo` | MetricAnalyst |
| 进程/资源 | `ps aux --sort=-rss`、`df -h /var/scratch` | ProcAnalyst |
| 网络 | `ping -c 3 <gw>`、`tc qdisc show`、`ss -s` | NetAnalyst |
