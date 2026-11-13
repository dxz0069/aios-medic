#!/bin/bash
# n10（等待 n9）：S1 切换vLLM+冒烟 → S2 v2h套件(vLLM时代数据) → S3 选择性固化快照 → S4 汇总
# 失败自动回退 stdlib。完成标记 NIGHTRUN10_DONE
N10=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
R=/public/home/acotxxttog/aios-medic
V=/root/proj4-devforge/.venv
echo "===== nightrun10 $N10 start $(date) ====="
for i in $(seq 1 240); do [ -f $WS/NIGHTRUN9_DONE ] && break; sleep 30; done
[ -f $WS/NIGHTRUN9_DONE ] && echo "[wait] N9完成" || echo "[wait] N9超时仍继续"

echo "[S1] 切换 vLLM $(date +%T)"
if MEDIC_TIMEOUT=560 $X $M/vllm_up.sh > $WS/vllm_up_10.log 2>&1; then
  echo "[S1] vLLM 就绪!"; touch $WS/VLLM_UP3
else
  echo "[S1] vLLM 失败(日志 vllm_up_10.log)，回退 stdlib"
  MEDIC_TIMEOUT=60 $X -c "pkill -f vllm.entrypoints" >/dev/null 2>&1
  MEDIC_TIMEOUT=420 $X $M/start_infer.sh >/dev/null 2>&1
fi
MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1
MEDIC_TIMEOUT=300 $X $M/agent_smoke.sh > $WS/agent_smoke_10.log 2>&1 && echo "[S1] 冒烟通过" || echo "[S1] 冒烟异常"

echo "[S2] v2h 套件 $(date +%T)"
NIGHTRUN2_TAG=v2h bash $M/nightrun2.sh >> $WS/nightrun10_console.log 2>&1 || echo "[S2] v2h 异常"

echo "[S3] 选择性固化快照(site-packages + 入口点 → NFS) $(date +%T)"
mkdir -p $WS/images
MEDIC_TIMEOUT=560 $X -c "cd /usr/local && tar -czf /public/home/acotxxttog/m1ws/images/syspython-vllm-1113.tar.gz lib/python3.11/site-packages bin 2>/dev/null; ls -la /public/home/acotxxttog/m1ws/images/ | head -3" || echo "[S3] 快照失败"
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v2h" >/dev/null 2>&1 || true
MEDIC_TIMEOUT=60 $X -c "cd $R && for f in F01 F03 F04 F05 F06 F10 F18; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun10 DONE $(date) ====="
touch $WS/NIGHTRUN10_DONE
