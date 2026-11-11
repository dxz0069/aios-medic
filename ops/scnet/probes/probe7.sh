#!/bin/bash
M=/public/home/acotxxttog/models/Qwen2.5-7B-Instruct
echo "=== 等待模型下载完成(最多8分钟) ==="
for i in $(seq 1 24); do
  sleep 20
  SZ=$(du -sm $M 2>/dev/null | cut -f1)
  RUNNING=$(pgrep -f "modelscope download" | head -1)
  echo "t=$((i*20))s size=${SZ}MB running=${RUNNING:+yes}"
  if [ -z "$RUNNING" ]; then break; fi
done
echo "=== 模型文件 ==="
ls -la $M 2>/dev/null | head -12
echo "=== 启动环境恢复(后台) ==="
setsid nohup tar -xf /public/home/acotxxttog/bw_image_migration_20261107/proj4-devforge.tar -C /root > /public/home/acotxxttog/restore_env.log 2>&1 < /dev/null &
echo "TAR_EXTRACT_STARTED"
