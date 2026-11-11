#!/bin/bash
cd /public/home/acotxxttog/aios-medic
echo "=== 启动推理服务(系统python/dtk torch) ==="
setsid nohup python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct --port 8091 > /public/home/acotxxttog/infer_server.log 2>&1 < /dev/null &
echo "SERVER_STARTING"
for i in $(seq 1 20); do
  sleep 12
  if curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok; then echo "SERVER_UP t=$((i*12))s"; break; fi
  echo "waiting... t=$((i*12))s"
done
head -5 /public/home/acotxxttog/infer_server.log
echo "=== 单发测试 ==="
curl -s --max-time 120 http://127.0.0.1:8091/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"只输出JSON: {\\\"ok\\\": true}\"}],\"temperature\":0,\"max_tokens\":50}" | head -c 600
echo; echo "=== 启动 Spike①(后台) ==="
setsid nohup python3 experiments/spike1/run_spike1.py --base-url http://127.0.0.1:8091/v1 --model qwen2.5-7b-instruct > /public/home/acotxxttog/spike1_run.log 2>&1 < /dev/null &
echo "SPIKE1_STARTED"
