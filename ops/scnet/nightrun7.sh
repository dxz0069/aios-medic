#!/bin/bash
# n7（等待 n6 完成）：S1 v3补跑(F02/F05) → S2 F03快照模式(采集后即清除,推理期无CPU争用)
#    → S3 Kernel路由策略对比(重试) → S4 汇总。完成标记 NIGHTRUN7_DONE
N7=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
A=/root/proj4-devforge/third_party/AIOS
echo "===== nightrun7 $N7 start $(date) ====="
for i in $(seq 1 240); do [ -f $WS/NIGHTRUN6_DONE ] && break; sleep 30; done
[ -f $WS/NIGHTRUN6_DONE ] && echo "[wait] N6完成" || echo "[wait] N6超时仍继续"

ensure_stack() {
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok" 2>/dev/null; then
    if [ -f $WS/VLLM_UP2 ]; then MEDIC_TIMEOUT=560 $X $M/vllm_up.sh >/dev/null 2>&1; else MEDIC_TIMEOUT=420 $X $M/start_infer.sh >/dev/null 2>&1; fi
  fi
  MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null \
    || MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true
}

echo "[S1] v3 补跑 $(date +%T)"
rm -f $WS/NIGHTRUN3_DONE
MEDIC_TIMEOUT=15 $X -c "rm -rf $WS/v3" >/dev/null 2>&1
N3_WAIT_MARKER=NIGHTRUN2_DONE bash $M/nightrun3.sh >> $WS/nightrun7_console.log 2>&1 || echo "[S1] v3 异常"
ensure_stack

echo "[S2] F03 快照模式(采集后清除,推理期无争用) $(date +%T)"
for ROUND in 1 2 3; do
  for MODE in serial concurrent; do
    ensure_stack
    D=$WS/f03snap/r$ROUND; mkdir -p $D
    if ! MEDIC_TIMEOUT=120 $X -c "cd $R && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py F03 --action inject && sleep 10 && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null && python3 testbed/injector/inject.py F03 --action clear && sleep 2"; then
      echo "[S2] r$ROUND $MODE 采集失败"; continue
    fi
    TMO=600; [ "$MODE" = "concurrent" ] && TMO=450
    MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd $R && timeout $TMO $V/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold F03 > $D/${MODE}.log 2>&1" || echo "[S2] r$ROUND $MODE 流水线异常"
    # 快照模式修复目标已不存在：清除残留(无害)
    MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py F03 --action clear >/dev/null 2>&1" || true
    echo "[S2] r$ROUND $MODE done $(date +%T)"
  done
done

echo "[S3] 路由策略对比(重试) $(date +%T)"
STRATS=$(MEDIC_TIMEOUT=40 $X -c "grep -rhoE 'sequential|priority|round_robin|roundrobin|fifo|random|shortest_queue|least_latency' $A/aios/llm_core/ 2>/dev/null | sort -u | head -6" 2>/dev/null | tr "\n" " ")
echo "[S3] 发现策略: ${STRATS:-none}"
for S in $STRATS; do
  [ "$S" = "sequential" ] && continue
  echo "[S3] == 策略 $S == $(date +%T)"
  MEDIC_TIMEOUT=60 $X -c "cd $A && sed -i \"s/strategy: .*/strategy: \\\"$S\\\"/\" aios/config/config.yaml && grep strategy aios/config/config.yaml | head -1" || continue
  MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || { echo "[S3] $S 内核失败"; continue; }
  for MODE in serial concurrent; do
    D=$WS/router/$S/r1; mkdir -p $D
    MEDIC_TIMEOUT=140 $X -c "cd $R && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py F03 --action inject && sleep 10 && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null && python3 testbed/injector/inject.py F03 --action clear" || continue
    TMO=600; [ "$MODE" = "concurrent" ] && TMO=450
    MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd $R && timeout $TMO $V/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold F03 > $D/${MODE}.log 2>&1" || echo "[S3] $S $MODE 异常"
  done
done
MEDIC_TIMEOUT=60 $X -c "cd $A && sed -i 's/strategy: .*/strategy: \"sequential\"/' aios/config/config.yaml" || true
MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true

echo "[S4] aggregate $(date +%T)"
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v3" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/f03snap" >/dev/null 2>&1 || true
[ -d $WS/router ] && MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/router" >/dev/null 2>&1 || true
echo "===== nightrun7 DONE $(date) ====="
touch $WS/NIGHTRUN7_DONE
