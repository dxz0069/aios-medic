#!/bin/bash
cd /public/home/acotxxttog/aios-medic
echo "=== flash-attn 安装情况 ==="
pip show flash-attn 2>/dev/null | head -3 || pip show flash_attn 2>/dev/null | head -3 || echo "pip查无flash-attn"
python3 -c "import flash_attn" 2>&1 | head -3
echo "=== 卸载 ==="
pip uninstall -y flash-attn flash_attn 2>&1 | grep -v WARNING | head -3
pkill -f run_spike1.py 2>/dev/null; pkill -f infer_server_stdlib 2>/dev/null; sleep 3
setsid nohup python3 tools/infer_server_stdlib.py --model /public/home/acotxxttog/models/Qwen2.5-7B-Instruct --port 8091 --attn sdpa > /public/home/acotxxttog/infer_server3.log 2>&1 < /dev/null &
for i in $(seq 1 25); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok; then echo "SERVER_UP t=$((i*10))s"; break; fi
done
echo "=== 单发测试 ==="
curl -s --max-time 180 http://127.0.0.1:8091/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"回复一个JSON: {\\\"ok\\\": true}\"}],\"temperature\":0,\"max_tokens\":60}" | head -c 700
