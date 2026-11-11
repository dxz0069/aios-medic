#!/bin/bash
cd /public/home/acotxxttog/aios-medic
pkill -f run_spike1.py 2>/dev/null; pkill -f infer_server_stdlib 2>/dev/null; sleep 3
echo "=== 重启推理服务(sdpa) ==="
setsid nohup python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct --port 8091 --attn sdpa > /public/home/acotxxttog/infer_server2.log 2>&1 < /dev/null &
for i in $(seq 1 25); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok; then echo "SERVER_UP t=$((i*10))s"; break; fi
done
echo "=== 单发测试 ==="
curl -s --max-time 180 http://127.0.0.1:8091/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"回复一个JSON: {\\\"ok\\\": true}\"}],\"temperature\":0,\"max_tokens\":60}" | head -c 700
echo; echo "=== 启动 Spike①(后台) ==="
setsid nohup python3 experiments/spike1/run_spike1.py --base-url http://127.0.0.1:8091/v1 --model qwen2.5-7b-instruct --timeout 180 > /public/home/acotxxttog/spike1_run2.log 2>&1 < /dev/null &
echo SPIKE1_RESTARTED
