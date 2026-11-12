#!/bin/bash
# 夜间追加任务5（等待 nightrun4 完成后自动接力）：
#   S1 v3补跑(F02/F05) → S2 vLLM重试(取证+修复+失败回退) → S3 v2g套件(组件提示词修复)
#   → S4 Kernel路由策略对比(运行时发现策略，无则跳过) → S5 汇总
# 完成标记：~/m1ws/NIGHTRUN5_DONE；日志：~/m1ws/nightrun5_console.log
N5=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
A=/root/proj4-devforge/third_party/AIOS
echo "===== nightrun5 $N5 start $(date) ====="

for i in $(seq 1 240); do [ -f $WS/NIGHTRUN4_DONE ] && break; sleep 30; done
[ -f $WS/NIGHTRUN4_DONE ] && echo "[wait] N4完成" || echo "[wait] N4超时(2h)仍继续"

ensure_kernel() {
  MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null \
    || MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true
}

echo "[S1] v3 补跑(F02/F05) $(date +%T)"
rm -f $WS/NIGHTRUN3_DONE
MEDIC_TIMEOUT=15 $X -c "rm -rf $WS/v3" >/dev/null 2>&1
N3_WAIT_MARKER=NIGHTRUN2_DONE bash $M/nightrun3.sh >> $WS/nightrun5_console.log 2>&1 || echo "[S1] v3 异常"
ensure_kernel

echo "[S2] vLLM 重试 $(date +%T)"
MEDIC_TIMEOUT=30 $X -c "grep -E 'Error|ERROR|Exception|No module' /public/home/acotxxttog/vllm_server.log 2>/dev/null | head -8 > $WS/vllm_fail_evidence.txt; wc -l < $WS/vllm_fail_evidence.txt"
MEDIC_TIMEOUT=560 $X $M/vllm_fixdeps.sh > $WS/vllm_fixdeps_5.log 2>&1 || true
if MEDIC_TIMEOUT=560 $X $M/vllm_up.sh > $WS/vllm_up_5.log 2>&1; then
  echo "[S2] vLLM 就绪! $(date +%T)"; touch $WS/VLLM_UP2
else
  echo "[S2] vLLM 仍失败(证据在 vllm_fail_evidence.txt)，继续 stdlib"
  MEDIC_TIMEOUT=60 $X -c "pkill -f vllm.entrypoints" >/dev/null 2>&1
  MEDIC_TIMEOUT=420 $X $M/start_infer.sh >/dev/null 2>&1 || true
fi
ensure_kernel
MEDIC_TIMEOUT=300 $X $M/agent_smoke.sh > $WS/agent_smoke_5.log 2>&1 && echo "[S2] 冒烟通过" || echo "[S2] 冒烟异常"

echo "[S3] v2g 套件(组件提示词修复版) $(date +%T)"
NIGHTRUN2_TAG=v2g bash $M/nightrun2.sh >> $WS/nightrun5_console.log 2>&1 || echo "[S3] v2g 异常"

echo "[S4] Kernel 路由策略对比 $(date +%T)"
STRATS=$(MEDIC_TIMEOUT=30 $X -c "grep -rhoE 'sequential|priority|round_robin|roundrobin|fifo|random' $A/aios/llm_core/ 2>/dev/null | sort -u | head -6" 2>/dev/null | tr "\n" " ")
echo "[S4] 代码中发现的策略: ${STRATS:-none}"
for S in $STRATS; do
  [ "$S" = "sequential" ] && continue
  echo "[S4] == 策略 $S == $(date +%T)"
  if ! MEDIC_TIMEOUT=60 $X -c "cd $A && sed -i \"s/strategy: .*/strategy: \\\"$S\\\"/\" aios/config/config.yaml && grep strategy aios/config/config.yaml | head -1"; then
    echo "[S4] $S 配置失败"; continue
  fi
  MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || { echo "[S4] $S 内核启动失败(回退)"; continue; }
  for ROUND in 1 2; do
    for MODE in serial concurrent; do
      D=$WS/router/$S/r$ROUND; mkdir -p $D
      MEDIC_TIMEOUT=140 $X -c "cd /public/home/acotxxttog/aios-medic && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py F03 --action inject && sleep 10 && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null && python3 testbed/injector/inject.py F03 --action clear" || { echo "[S4] $S r$ROUND 采集失败"; continue; }
      TMO=600; [ "$MODE" = "concurrent" ] && TMO=450
      MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd /public/home/acotxxttog/aios-medic && timeout $TMO /root/proj4-devforge/.venv/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold F03 > $D/${MODE}.log 2>&1" || echo "[S4] $S r$ROUND $MODE 流水线异常"
    done
  done
done
echo "[S4] 恢复 sequential 策略"
MEDIC_TIMEOUT=60 $X -c "cd $A && sed -i 's/strategy: .*/strategy: \"sequential\"/' aios/config/config.yaml && grep strategy aios/config/config.yaml | head -1" || true
MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true

echo "[S5] aggregate $(date +%T)"
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v2g" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v3" >/dev/null 2>&1 || true
[ -d $WS/router ] && MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/router" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=60 $X -c "cd /public/home/acotxxttog/aios-medic && for f in F01 F03 F04 F05; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun5 DONE $(date) ====="
touch $WS/NIGHTRUN5_DONE
