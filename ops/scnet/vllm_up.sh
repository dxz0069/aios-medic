#!/bin/bash
# 切换到 vLLM(DAS) 推理服务（替换 stdlib 微批服务）。端口沿用 8091，Kernel 配置无需改动。
# 说明：--enforce-eager 规避 DTK 上 CUDA Graph 捕获问题（CSDN 海光BW部署实践）；
#       --max-model-len 8192 控制 KV cache 上限；gpu-memory-utilization 0.85。
set -uo pipefail
R=/public/home/acotxxttog/aios-medic
M=/public/home/acotxxttog/models/Qwen2.5-7B-Instruct
pkill -f infer_server_stdlib 2>/dev/null
pkill -f vllm.entrypoints 2>/dev/null
sleep 3
setsid nohup python3 -m vllm.entrypoints.openai.api_server \
  --model "$M" --served-model-name qwen2.5-7b-instruct \
  --dtype bfloat16 --enforce-eager \
  --max-model-len 8192 --gpu-memory-utilization 0.85 \
  --host 0.0.0.0 --port 8091 > /public/home/acotxxttog/vllm_server.log 2>&1 < /dev/null &
echo "VLLM_LAUNCHING (日志 ~/vllm_server.log)"
for i in $(seq 1 45); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/v1/models 2>/dev/null | grep -q qwen; then
    echo "VLLM_UP t=$((i*10))s"
    curl -s --max-time 30 http://127.0.0.1:8091/v1/chat/completions -H "Content-Type: application/json" \
      -d '{"model":"qwen2.5-7b-instruct","messages":[{"role":"user","content":"只输出JSON: {\"ok\": true}"}],"temperature":0,"max_tokens":40}' | head -c 300
    echo
    exit 0
  fi
done
echo "VLLM 未在450s内就绪，查 ~/vllm_server.log"
exit 1
