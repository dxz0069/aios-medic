#!/bin/bash
# n9（立即可跑）：v6c 新故障终轮（采集器僵尸可见性+诊断端口提示） + v3 补跑（无争用窗口）
N9=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
echo "===== nightrun9 $N9 start $(date) ====="
ensure_stack() {
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok" 2>/dev/null; then
    if [ -f $WS/VLLM_UP2 ]; then MEDIC_TIMEOUT=560 $X $M/vllm_up.sh >/dev/null 2>&1; else MEDIC_TIMEOUT=420 $X $M/start_infer.sh >/dev/null 2>&1; fi
  fi
  MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null \
    || MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || true
}
declare -A WAIT2=( [F06]=12 [F10]=25 [F18]=12 )
echo "[S1] v6c 新故障终轮 $(date +%T)"
for F in F06 F10 F18; do
  for ROUND in 1 2; do
    for MODE in serial concurrent; do
      ensure_stack
      D=$WS/v6c/$F/r$ROUND; mkdir -p $D
      W=${WAIT2[$F]}
      if ! MEDIC_TIMEOUT=$((W+90)) $X -c "cd $R && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py $F --action inject && sleep $W && python3 testbed/collect/collect.py --out $D/fault_$MODE.json >/dev/null"; then
        echo "[n9] $F r$ROUND $MODE 注入失败"; MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true; continue
      fi
      TMO=600; [ "$MODE" = "concurrent" ] && TMO=450
      MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd $R && timeout $TMO $V/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault_$MODE.json --mode $MODE --out $D --gold $F > $D/${MODE}.log 2>&1" || echo "[n9] $F r$ROUND $MODE 异常"
      MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
      sleep 3
    done
  done
done
echo "[S2] v3 补跑 $(date +%T)"
rm -f $WS/NIGHTRUN3_DONE
MEDIC_TIMEOUT=15 $X -c "rm -rf $WS/v3" >/dev/null 2>&1
N3_WAIT_MARKER=NIGHTRUN2_DONE bash $M/nightrun3.sh >> $WS/nightrun9_console.log 2>&1 || echo "[S2] v3 异常"
echo "[S3] aggregate $(date +%T)"
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v6c" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v3" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05 F06 F10 F18; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun9 DONE $(date) ====="
touch $WS/NIGHTRUN9_DONE
