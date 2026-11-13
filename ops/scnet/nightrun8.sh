#!/bin/bash
# n8（等待 n7）：新故障套件复跑（修复 actions 白名单漏加 + 进程自标识后）
# 完成标记 NIGHTRUN8_DONE
N8=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
echo "===== nightrun8 $N8 start $(date) ====="
for i in $(seq 1 240); do [ -f $WS/NIGHTRUN7_DONE ] && break; sleep 30; done
[ -f $WS/NIGHTRUN7_DONE ] && echo "[wait] N7完成" || echo "[wait] N7超时仍继续"

ensure_stack() {
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok" 2>/dev/null; then
    if [ -f $WS/VLLM_UP2 ]; then MEDIC_TIMEOUT=560 $X $M/vllm_up.sh >/dev/null 2>&1; else MEDIC_TIMEOUT=420 $X $M/start_infer.sh >/dev/null 2>&1; fi
  fi
  MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null \
    || MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true
}

declare -A WAIT2=( [F06]=12 [F10]=25 [F18]=12 )
for F in F06 F10 F18; do
  for ROUND in 1 2; do
    for MODE in serial concurrent; do
      ensure_stack
      D=$WS/v6b/$F/r$ROUND; mkdir -p $D
      W=${WAIT2[$F]}
      if ! MEDIC_TIMEOUT=$((W+90)) $X -c "cd $R && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py $F --action inject && sleep $W && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null"; then
        echo "[n8] $F r$ROUND $MODE 注入失败"
        MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
        continue
      fi
      TMO=600; [ "$MODE" = "concurrent" ] && TMO=450
      MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd $R && timeout $TMO $V/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold $F > $D/${MODE}.log 2>&1" || echo "[n8] $F r$ROUND $MODE 流水线异常"
      MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
      sleep 3
      echo "[n8] $F r$ROUND $MODE done $(date +%T)"
    done
  done
done
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v6b" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05 F06 F10 F18; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun8 DONE $(date) ====="
touch $WS/NIGHTRUN8_DONE
