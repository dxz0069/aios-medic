#!/bin/bash
# 启动 AIOS Kernel（已在运行则先杀）。前置：推理服务 :8091 存活（start_infer.sh）。
# 说明：memory 必须用 in-house provider（mem0 会连 Ollama 导致启动失败）；
#       端口固定 8000（launch.py 默认）；启动约需 1-2 分钟（LiteLLM 网络重试较慢属正常）。
set -uo pipefail
A=/root/proj4-devforge/third_party/AIOS
C=/root/proj4-devforge/third_party/Cerebrum
V=/root/proj4-devforge/.venv

cat > $A/aios/config/config.yaml << "CFG"
api_keys:
  openai: "EMPTY"
llms:
  models:
    - name: "qwen2.5-7b-instruct"
      backend: "vllm"
      hostname: "http://localhost:8091/v1"
  router:
    strategy: "sequential"
memory:
  provider: "in-house"
  in_house:
    vector_db_backend: "chroma"
storage:
  root_dir: "root"
  use_vector_db: false
CFG

curl -s --max-time 3 http://127.0.0.1:8091/health | grep -q ok || { echo "推理服务未运行，先跑 start_infer.sh"; exit 1; }
cd $A
pkill -f "runtime/launch.py" 2>/dev/null; sleep 2
setsid nohup env PYTHONPATH=$A $V/bin/python runtime/launch.py > /public/home/acotxxttog/kernel.log 2>&1 < /dev/null &
echo "KERNEL_LAUNCHING (日志: ~/kernel.log)"
for i in $(seq 1 30); do
  sleep 6
  if curl -s --max-time 3 http://127.0.0.1:8000/core/llms/list 2>/dev/null | grep -q success; then
    echo "KERNEL_UP t=$((i*6))s"; break
  fi
  pgrep -f "runtime/launch.py" >/dev/null || { echo "进程已退出，查 ~/kernel.log"; exit 1; }
done
curl -s --max-time 5 http://127.0.0.1:8000/core/llms/list; echo
# 回写 Cerebrum 侧 kernel 地址
$V/bin/python - << PYEOF
import yaml, pathlib
p = pathlib.Path("$C/cerebrum/config/config.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
cfg.setdefault("kernel", {})["base_url"] = "http://127.0.0.1:8000"
p.write_text(yaml.safe_dump(cfg, allow_unicode=True))
print("cerebrum kernel.base_url ->", cfg["kernel"]["base_url"])
PYEOF
