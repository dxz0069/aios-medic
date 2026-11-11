#!/bin/bash
# Medic 夜间自主构建 第二阶段（全闭环 v2：诊断→修复-验证回环→报告）
# 前置：等待第一阶段 nightrun.sh 完成（NIGHTRUN_DONE），随后自动执行。
# 产物：/public/home/acotxxttog/m1ws/v2/<Fxx>/r<N>/{serial,concurrent}-v2-*/...
#       + night2_summary.{json,md} + NIGHTRUN2_DONE
NIGHTRUN2_VERSION=v1
set -uo pipefail
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
mkdir -p $WS/v2
echo "===== nightrun2 $NIGHTRUN2_VERSION start $(date) ====="

echo "[wait] 等待第一阶段 NIGHTRUN_DONE ..."
for i in $(seq 1 150); do
  [ -f $WS/NIGHTRUN_DONE ] && { echo "[wait] 第一阶段完成"; break; }
  sleep 60
done
[ -f $WS/NIGHTRUN_DONE ] || echo "[wait] 超时（150分钟），直接开始第二阶段"

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

# 玩具服务保活（F04 修复验证依赖）+ 清理可能的僵尸流水线 + 尝试装 iproute2(F05)
MEDIC_TIMEOUT=60 $X -c "pgrep -f supervisor.py >/dev/null || setsid nohup python3 /opt/medic/service/supervisor.py >/dev/null 2>&1 & sleep 3; curl -s --max-time 3 http://127.0.0.1:8080/health | head -c 60; echo"
MEDIC_TIMEOUT=60 $X -c "pkill -f run_pipeline; pkill -f 'import multiprocessing as mp'; pkill -f leaky; pkill -f 'signal.SIGKILL'; sleep 1; echo busy_left=\$(pgrep -fc 'import multiprocessing as mp' || echo 0) zombies=\$(pgrep -f run_pipeline | wc -l)"
MEDIC_TIMEOUT=90 $X -c "source /public/home/acotxxttog/.ai_user_info/ai_proxy 2>/dev/null; which tc || apt-get install -y iproute2 2>&1 | head -2; which tc || echo tc-unavailable"
ensure_stack

run_fault() {  # $1=故障id $2=注入后等待秒
  local F=$1 WAIT=$2 ROUND D MODE
  for ROUND in 1 2 3; do
    for MODE in serial concurrent; do
      ensure_stack
      D=$WS/v2/$F/r$ROUND; mkdir -p $D
      echo "---- v2 $F r$ROUND $MODE $(date +%T) ----"
      if ! MEDIC_TIMEOUT=$((WAIT+90)) $X -c "cd $R && mkdir -p /var/scratch && python3 testbed/injector/inject.py $F --action inject && sleep $WAIT && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null"; then
        echo "[skip] $F r$ROUND $MODE 注入/采集失败"
        echo "{\"fault\":\"$F\",\"round\":$ROUND,\"mode\":\"$MODE\",\"stage\":\"inject\",\"error\":\"failed\"}" > $D/inject_failed_$MODE.json
        MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
        continue
      fi
      MEDIC_TIMEOUT=480 $X -c "cd $R && timeout 400 $V/bin/python experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold $F > $D/${MODE}.log 2>&1" \
        || echo "[warn] $F r$ROUND $MODE v2流水线异常(超时?)"
      MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
      sleep 3
      echo "[$F r$ROUND $MODE done] $(date +%T)"
    done
  done
}

run_fault F03 10
run_fault F01 120
run_fault F04 15
run_fault F05 8

echo "===== aggregate2 $(date +%T) ====="
MEDIC_TIMEOUT=120 $X -c "python3 /public/home/acotxxttog/medic/aggregate_m1.py --ws $WS/v2" || echo "[warn] 汇总失败"
MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun2 DONE $(date) ====="
touch $WS/NIGHTRUN2_DONE
