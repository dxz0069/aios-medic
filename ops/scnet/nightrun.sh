#!/bin/bash
# Medic 夜间自主构建（登录节点上 setsid 运行，断开 SSH / 客户端关机不影响）
# 内容：故障套件 {F03 CPU, F01 内存泄漏, F04 服务崩溃, F05 网络丢包(视权限)} ×
#       {注入→采集→清除} × {serial, concurrent} 流水线 × 3 轮 + 汇总报告
# 产物：/public/home/acotxxttog/m1ws/ 下各故障目录 + night_summary.{json,md}
NIGHTRUN_VERSION=v1
set -uo pipefail
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
mkdir -p $WS
echo "===== nightrun $NIGHTRUN_VERSION start $(date) ====="

ensure_stack() {
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok" 2>/dev/null; then
    echo "[ensure] $(date +%T) 重启推理服务"
    MEDIC_TIMEOUT=420 $X /public/home/acotxxttog/medic/start_infer.sh || echo "[ensure] 推理服务启动失败"
  fi
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null; then
    echo "[ensure] $(date +%T) 重启 Kernel"
    MEDIC_TIMEOUT=420 $X /public/home/acotxxttog/medic/kernel_up.sh || echo "[ensure] Kernel 启动失败"
  fi
}

# 阶段0：清理残留故障 + 部署玩具服务(F04) + 确保栈可用
MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; mkdir -p /opt/medic /var/scratch && cp -r $R/testbed/sandbox/service /opt/medic/ 2>/dev/null; pgrep -f supervisor.py >/dev/null || setsid nohup python3 /opt/medic/service/supervisor.py >/dev/null 2>&1 & sleep 3; curl -s --max-time 3 http://127.0.0.1:8080/health | head -c 60; echo"
MEDIC_TIMEOUT=60 $X -c "pkill -f infer_server_stdlib" 2>/dev/null; sleep 3   # 强制换新(微批处理)版
ensure_stack

run_fault() {  # $1=故障id $2=注入后等待秒
  local F=$1 WAIT=$2 ROUND D
  for ROUND in 1 2 3; do
    ensure_stack
    D=$WS/$F/r$ROUND; mkdir -p $D
    echo "---- $F round $ROUND $(date +%T) ----"
    if ! MEDIC_TIMEOUT=$((WAIT+90)) $X -c "cd $R && python3 testbed/injector/inject.py $F --action inject && sleep $WAIT && python3 testbed/collect/collect.py --out $D/fault.json >/dev/null && python3 testbed/injector/inject.py $F --action clear && sleep 2"; then
      echo "[skip] $F r$ROUND 注入/采集失败（记录后继续）"
      echo "{\"fault\":\"$F\",\"round\":$ROUND,\"stage\":\"inject\",\"error\":\"failed\"}" > $D/inject_failed.json
      MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
      continue
    fi
    MEDIC_TIMEOUT=280 $X -c "cd $R && $V/bin/python experiments/m1_demo/run_pipeline.py --collection $D/fault.json --mode serial --out $D --gold $F > $D/serial.log 2>&1" \
      || echo "[warn] $F r$ROUND serial 异常(超时?)"
    MEDIC_TIMEOUT=280 $X -c "cd $R && $V/bin/python experiments/m1_demo/run_pipeline.py --collection $D/fault.json --mode concurrent --out $D --gold $F > $D/concurrent.log 2>&1" \
      || echo "[warn] $F r$ROUND concurrent 异常(超时?)"
    echo "[$F r$ROUND done] $(date +%T)"
  done
}

run_fault F03 10     # CPU 饱和
run_fault F01 120    # 内存泄漏（2 分钟 ≈ 30GB RSS）
run_fault F04 15     # 服务崩溃循环
run_fault F05 8      # 网络丢包（无 NET_ADMIN 则注入失败自动跳过）

echo "===== aggregate $(date +%T) ====="
MEDIC_TIMEOUT=120 $X -c "python3 /public/home/acotxxttog/medic/aggregate_m1.py --ws $WS" || echo "[warn] 汇总失败"

MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun DONE $(date) ====="
touch $WS/NIGHTRUN_DONE
