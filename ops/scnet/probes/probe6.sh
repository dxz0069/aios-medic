#!/bin/bash
source /public/home/acotxxttog/.ai_user_info/ai_proxy 2>/dev/null
echo "=== freeze-cerebrum.txt (前20行) ==="
head -20 /public/home/acotxxttog/proj4-reqs/work/freeze-cerebrum.txt 2>/dev/null
echo; echo "=== Cerebrum 目录 ==="
find /public/home/acotxxttog/proj4-reqs/third_party/Cerebrum -maxdepth 1 2>/dev/null | head -15
echo; echo "=== tar 内容扫描(vllm/venv/site-packages) ==="
timeout 280 tar -tf /public/home/acotxxttog/bw_image_migration_20261107/proj4-devforge.tar 2>/dev/null | grep -iE "vllm|site-packages|venv/bin/python" | head -15
echo "TAR_SCAN_DONE"
echo; echo "=== 正确CLI重启模型下载 ==="
setsid nohup modelscope download --model Qwen/Qwen2.5-7B-Instruct --local_dir /public/home/acotxxttog/models/Qwen2.5-7B-Instruct > /public/home/acotxxttog/dl_model3.log 2>&1 < /dev/null &
sleep 25
head -6 /public/home/acotxxttog/dl_model3.log; du -sh /public/home/acotxxttog/models/Qwen2.5-7B-Instruct 2>/dev/null
