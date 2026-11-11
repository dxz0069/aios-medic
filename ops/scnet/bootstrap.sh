#!/bin/bash
# 新容器一键恢复（72小时到期后）。在登录节点执行:
#   ~/medic/x /public/home/acotxxttog/medic/bootstrap.sh
set -uo pipefail

VENV=/root/proj4-devforge/.venv
TAR=/public/home/acotxxttog/bw_image_migration_20261107/proj4-devforge.tar
MODEL=/public/home/acotxxttog/models/Qwen2.5-7B-Instruct
REPO=/public/home/acotxxttog/aios-medic

echo "[1/3] 恢复 .venv 环境（aios-agent-sdk/Cerebrum）..."
if [ -x "$VENV/bin/python" ]; then
  echo "  .venv 已存在，跳过"
else
  tar -xf "$TAR" -C /root
  echo "  解压完成"
fi

echo "[2/3] 启动推理服务(:8091, eager)..."
pkill -f infer_server_stdlib 2>/dev/null; sleep 2
cd "$REPO" || exit 1
setsid nohup python3 tools/infer_server_stdlib.py --model "$MODEL" --port 8091 --attn eager \
  > /public/home/acotxxttog/infer_server.log 2>&1 < /dev/null &
UP=0
for i in $(seq 1 30); do
  sleep 10
  if curl -s --max-time 3 http://127.0.0.1:8091/health 2>/dev/null | grep -q ok; then
    echo "  服务就绪 t=$((i*10))s"; UP=1; break
  fi
done
[ "$UP" = 1 ] || { echo "  警告: 服务未在 300s 内就绪，查看 ~/infer_server.log"; }

echo "[3/3] 健康检查..."
"$VENV/bin/python" -c "import cerebrum, aios; print('  aios-sdk venv OK')" 2>&1 | head -1
ls "$MODEL"/model-00004-of-00004.safetensors >/dev/null 2>&1 && echo "  模型文件 OK" || echo "  警告: 模型文件缺失"
curl -s --max-time 5 http://127.0.0.1:8091/v1/models 2>/dev/null | head -c 120; echo
echo "bootstrap 完成"
