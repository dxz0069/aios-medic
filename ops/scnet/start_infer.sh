#!/bin/bash
# 单独启动/重启推理服务（系统 python + dtk torch + eager attention）。
set -uo pipefail
MODEL=${MODEL:-/public/home/acotxxttog/models/Qwen2.5-7B-Instruct}
REPO=/public/home/acotxxttog/aios-medic
pkill -f infer_server_stdlib 2>/dev/null; sleep 2
cd "$REPO" || exit 1
setsid nohup python3 tools/infer_server_stdlib.py --model "$MODEL" --port 8091 --attn eager \
  --batch-window-ms "${BATCH_WINDOW_MS:-500}" --max-batch "${MAX_BATCH:-8}" \
  > /public/home/acotxxttog/infer_server.log 2>&1 < /dev/null &
echo "启动中，日志: /public/home/acotxxttog/infer_server.log"
for i in $(seq 1 30); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/health 2>/dev/null | grep -q ok; then
    echo "服务就绪 t=$((i*10))s"; exit 0
  fi
done
echo "300s 未就绪"; exit 1
