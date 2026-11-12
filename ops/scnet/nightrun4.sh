#!/bin/bash
# 夜间长任务 v4（目标 ≥6h），登录节点 setsid 运行，断连不影响。
# 阶段：S1 vLLM切换(失败自动回退stdlib) → S2 n3(F02/F05) → S3 三轮套件(v2d/v2e/v2f)
#      → S5 稳定性soak(18轮并发全闭环轮换故障) → S6 总汇总
# 完成标记：~/m1ws/NIGHTRUN4_DONE；总控日志：~/m1ws/nightrun4_console.log
N4=v1
set -uo pipefail
WS=/public/home/acotxxttog/m1ws
X=/public/home/acotxxttog/medic/x
M=/public/home/acotxxttog/medic
echo "===== nightrun4 $N4 start $(date) ====="

# ---- S1: vLLM 依赖补齐与切换（失败自动回退，保证夜跑不空转）----
echo "[S1] vLLM 依赖检查 $(date +%T)"
if ! MEDIC_TIMEOUT=20 $X -c "grep -q PIPBATCH_DONE /public/home/acotxxttog/vllm_batch.log" 2>/dev/null; then
  echo "[S1] 批量安装进行中，等待(最多25分钟)"
  for i in $(seq 1 50); do
    sleep 30
    MEDIC_TIMEOUT=15 $X -c "grep -q PIPBATCH_DONE /public/home/acotxxttog/vllm_batch.log" 2>/dev/null && break
  done
fi
MEDIC_TIMEOUT=560 $X $M/vllm_fixdeps.sh > $WS/vllm_fixdeps_final.log 2>&1 || true
if MEDIC_TIMEOUT=560 $X $M/vllm_up.sh > $WS/vllm_up_night.log 2>&1; then
  echo "[S1] vLLM 就绪 $(date +%T)"; touch $WS/VLLM_UP
else
  echo "[S1] vLLM 启动失败，回退 stdlib 推理服务 $(date +%T)"
  MEDIC_TIMEOUT=60 $X -c "pkill -f vllm.entrypoints" >/dev/null 2>&1
  MEDIC_TIMEOUT=420 $X $M/start_infer.sh || echo "[S1] 回退也失败!"
  touch $WS/VLLM_FAILED
fi
MEDIC_TIMEOUT=420 $X $M/kernel_up.sh >/dev/null 2>&1 || echo "[S1] kernel 异常"
MEDIC_TIMEOUT=300 $X $M/agent_smoke.sh > $WS/agent_smoke_night.log 2>&1 \
  && echo "[S1] 端到端冒烟通过" || echo "[S1] agent_smoke 异常(详见 agent_smoke_night.log)"
sleep 10

# ---- S2: F02/F05 外部证据诊断（n3）----
echo "[S2] n3 F02/F05 $(date +%T)"
rm -f $WS/NIGHTRUN3_DONE
MEDIC_TIMEOUT=15 $X -c "rm -rf /public/home/acotxxttog/m1ws/v3" >/dev/null 2>&1
N3_WAIT_MARKER=NIGHTRUN2_DONE bash $M/nightrun3.sh >> $WS/nightrun4_console.log 2>&1 || echo "[S2] n3 异常"
sleep 10

# ---- S3: 三轮全量套件（vLLM 时代数据 + 方差）----
for TAG in v2d v2e v2f; do
  echo "[S3] 套件 $TAG $(date +%T)"
  NIGHTRUN2_TAG=$TAG bash $M/nightrun2.sh >> $WS/nightrun4_console.log 2>&1 || echo "[S3] $TAG 异常"
  sleep 15
done

# ---- S5: 稳定性 soak（18 轮并发全闭环，轮换 F03/F04/F01）----
echo "[S5] soak 18轮 $(date +%T)"
V=/root/proj4-devforge/.venv
R=/public/home/acotxxttog/aios-medic
mkdir -p $WS/soak
for i in $(seq 1 18); do
  case $((i % 3)) in
    0) F=F03; W=10;; 1) F=F04; W=15;; 2) F=F01; W=120;;
  esac
  D=$WS/soak/c$i; mkdir -p $D
  echo "---- soak $i ($F) $(date +%T) ----"
  if ! MEDIC_TIMEOUT=$((W+90)) $X -c "cd $R && : > /var/log/medic/service.log 2>/dev/null; rm -f /var/log/medic/leaky.log; python3 testbed/injector/inject.py $F --action inject && sleep $W && python3 testbed/collect/collect.py --out $D/fault.json >/dev/null"; then
    echo "[soak] $i 注入失败"
    MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
    continue
  fi
  MEDIC_TIMEOUT=520 $X -c "cd $R && timeout 420 $V/bin/python -u experiments/m1_demo/run_pipeline_v2.py --collection $D/fault.json --mode concurrent --out $D --gold $F > $D/run.log 2>&1" \
    || echo "[soak] $i 流水线异常(超时?)"
  MEDIC_TIMEOUT=60 $X -c "cd $R && python3 testbed/injector/inject.py $F --action clear >/dev/null 2>&1" || true
  sleep 5
done

# ---- S6: 总汇总 ----
echo "[S6] aggregate $(date +%T)"
for T in v2d v2e v2f; do
  MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/$T" >/dev/null 2>&1 || echo "[S6] $T 汇总失败"
done
MEDIC_TIMEOUT=120 $X -c "python3 $M/aggregate_m1.py --ws $WS/v3" >/dev/null 2>&1 || true
SOAK_OK=$(python3 - << 'PYEOF'
import json, glob
ok = tot = 0
for f in glob.glob("/public/home/acotxxttog/m1ws/soak/c*/summary.json"):
    d = json.load(open(f)); tot += 1
    g = d.get("gold") or {}
    ok += 1 if (g.get("category_ok") and d.get("recovery_ok")) else 0
print(f"{ok}/{tot}")
PYEOF
)
echo "[S6] soak 类目+恢复双通过: $SOAK_OK"
MEDIC_TIMEOUT=60 $X -c "cd /root/proj4-devforge/third_party/AIOS 2>/dev/null; cd /public/home/acotxxttog/aios-medic && for f in F01 F03 F04 F05; do python3 testbed/injector/inject.py \$f --action clear >/dev/null 2>&1; done; echo cleaned"
echo "===== nightrun4 DONE $(date) ====="
touch $WS/NIGHTRUN4_DONE
