#!/bin/bash
cd /public/home/acotxxttog/aios-medic
echo "=== 报错字符串出处 ==="
grep -rl "No matching libraries found" /usr/local/lib/python3.11/site-packages/ 2>/dev/null | head -3
pkill -f infer_server_stdlib 2>/dev/null; sleep 3
setsid nohup python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct --port 8091 --attn eager > /public/home/acotxxttog/infer_server4.log 2>&1 < /dev/null &
for i in $(seq 1 25); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok; then echo "SERVER_UP(eager) t=$((i*10))s"; break; fi
done
echo "=== 单发测试 ==="
curl -s --max-time 180 http://127.0.0.1:8091/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"只输出JSON对象: {\\\"ok\\\": true}\"}],\"temperature\":0,\"max_tokens\":60}" | head -c 700
echo; echo "=== 启动 Spike① ==="
setsid nohup python3 experiments/spike1/run_spike1.py --base-url http://127.0.0.1:8091/v1 --model qwen2.5-7b-instruct --timeout 180 > /public/home/acotxxttog/spike1_run3.log 2>&1 < /dev/null &
echo SPIKE1_RUNNING
