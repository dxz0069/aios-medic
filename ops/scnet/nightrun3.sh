#!/bin/bash
# Medic 第三阶段v2：重跑外部证据诊断（配合时间窗提示词修复：F02/F05 证据包已用清洁日志重采）
# F02/F05 在服务器容器不可注入（无Docker/tc），采用"本地注入采集 + 服务器诊断"模式；
# 修复-验证阶段对这两种故障标记 N/A（闭环覆盖由 F01/F03/F04 现场验证）。
# 前置：等待 NIGHTRUN2_DONE。产物：~/m1ws/v3/<Fxx>/r<N>/{serial,concurrent}-*/summary.json
NIGHTRUN3_VERSION=v1
set -uo pipefail
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
mkdir -p $WS/v3
echo "===== nightrun3 $NIGHTRUN3_VERSION start $(date) ====="

echo "[wait] 等待 NIGHTRUN2_DONE ..."
for i in $(seq 1 180); do
  [ -f $WS/NIGHTRUN2_DONE ] && { echo "[wait] 第二阶段完成"; break; }
  sleep 60
done
[ -f $WS/NIGHTRUN2_DONE ] || echo "[wait] 超时（180分钟），直接开始"

ensure_stack() {
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok" 2>/dev/null; then
    echo "[ensure] $(date +%T) 重启推理服务"
    MEDIC_TIMEOUT=420 $X /public/home/acotxxttog/medic/start_infer.sh || true
  fi
  if ! MEDIC_TIMEOUT=15 $X -c "curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list | grep -q success" 2>/dev/null; then
    echo "[ensure] $(date +%T) 重启 Kernel"
    MEDIC_TIMEOUT=420 $X /public/home/acotxxttog/medic/kernel_up.sh || true
  fi
}

for F in F02 F05; do
  for ROUND in 1 2 3; do
    for MODE in serial concurrent; do
      ensure_stack
      D=$WS/v3/$F/r$ROUND; mkdir -p $D
      echo "---- v3 $F r$ROUND $MODE $(date +%T) ----"
      TMO=360; [ "$MODE" = "concurrent" ] && TMO=300
      MEDIC_TIMEOUT=$((TMO+120)) $X -c "cd $R && timeout $TMO $V/bin/python -u experiments/m1_demo/run_pipeline.py --collection $WS/ext/fault_$F.json --mode $MODE --out $D --gold $F > $D/${MODE}.log 2>&1" \
        || echo "[warn] $F r$ROUND $MODE 异常"
      echo "[$F r$ROUND $MODE done] $(date +%T)"
    done
  done
done

echo "===== aggregate3 $(date +%T) ====="
MEDIC_TIMEOUT=120 $X -c "python3 /public/home/acotxxttog/medic/aggregate_m1.py --ws $WS/v3" || true
echo "===== nightrun3 DONE $(date) ====="
touch $WS/NIGHTRUN3_DONE
