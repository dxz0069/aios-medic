#!/bin/bash
# 新容器一键恢复（72小时到期后）。在登录节点执行:
#   ~/medic/x /public/home/acotxxttog/medic/bootstrap.sh
# 恢复链：.venv(诊断) → vLLM(若wheel在位则自动安装,失败退化stdlib) → 推理服务 → Kernel → 三项检查
set -uo pipefail
VENV=/root/proj4-devforge/.venv
TAR=/public/home/acotxxttog/bw_image_migration_20261107/proj4-devforge.tar
MODEL=/public/home/acotxxttog/models/Qwen2.5-7B-Instruct
REPO=/public/home/acotxxttog/aios-medic
WHEELS=/public/home/acotxxttog/medic/wheels

echo "[1/4] 恢复 .venv 环境（aios-agent-sdk/Cerebrum）..."
if [ -x "$VENV/bin/python" ]; then
  echo "  .venv 已存在，跳过"
else
  tar -xf "$TAR" -C /root
  echo "  解压完成"
fi

echo "[2/4] vLLM 检查/安装..."
if python3 -c "import vllm" 2>/dev/null; then
  echo "  vllm 已可用"
else
  source /public/home/acotxxttog/.ai_user_info/ai_proxy 2>/dev/null
  WH=$(ls $WHEELS/vllm-*.whl 2>/dev/null | head -1)
  if [ -n "$WH" ]; then
    pip install --no-deps -q "$WH" && python3 /public/home/acotxxttog/medic/fixdeps.py || echo "  vllm 安装异常(将使用stdlib推理)"
  else
    echo "  无wheel，使用stdlib推理服务"
  fi
fi

echo "[3/4] 启动推理服务..."
if python3 -c "import vllm" 2>/dev/null && bash /public/home/acotxxttog/medic/vllm_up.sh; then
  echo "  vLLM 服务已就绪"
else
  pkill -f vllm.entrypoints 2>/dev/null
  bash /public/home/acotxxttog/medic/start_infer.sh || echo "  警告: 推理服务未就绪"
fi
echo "[4/4] Kernel 与健康检查..."
bash /public/home/acotxxttog/medic/kernel_up.sh >/dev/null 2>&1 || echo "  警告: Kernel 异常"
"$VENV/bin/python" -c "import cerebrum, aios; print('  aios-sdk venv OK')" 2>&1 | head -1
ls "$MODEL"/model-00004-of-00004.safetensors >/dev/null 2>&1 && echo "  模型文件 OK" || echo "  警告: 模型文件缺失"
curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list 2>/dev/null | head -c 120; echo
echo "bootstrap 完成"
