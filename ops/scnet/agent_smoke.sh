#!/bin/bash
# Medic 智能体端到端冒烟：run-agent → LogAnalyst → Kernel(:8000) → 推理服务(:8091)。
# 用 Spike① 样本 S01（dmesg OOM）作为输入，期望输出 resource/memory + leaky.py。
set -uo pipefail
C=/root/proj4-devforge/third_party/Cerebrum
V=/root/proj4-devforge/.venv
R=/public/home/acotxxttog/aios-medic

curl -s --max-time 3 http://127.0.0.1:8000/core/llms/list | grep -q success || { echo "Kernel 未运行，先跑 kernel_up.sh"; exit 1; }

SNIP=$($V/bin/python -c "import json;d=json.load(open(\"$R/experiments/spike1/samples/samples_f01_memory.json\"));s=d[\"samples\"][0];print(json.dumps({\"source\":s[\"source\"],\"snippet\":s[\"snippet\"]},ensure_ascii=False))")
echo "输入: S01 (dmesg OOM 样本)"
cd $C
timeout 300 $V/bin/run-agent --mode local --agent_path $R/agents/log_analyst --task_input "$SNIP" 2>&1 \
  | grep -E "Running agent|Result:|ERROR" | head -5
