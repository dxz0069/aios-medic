#!/bin/bash
echo "=== proj4-reqs 目录 ==="
ls -la /public/home/acotxxttog/proj4-reqs/ 2>&1 | head -25
echo; echo "=== 最新 wheel-dl6.log ==="
head -25 /public/home/acotxxttog/wheel-dl6.log 2>&1
echo; echo "=== 全局找 vllm wheel ==="
find /public/home/acotxxttog -maxdepth 3 -iname "*vllm*" 2>/dev/null | head -10
echo; echo "=== modelscope 可用性 ==="
python3 -c "import modelscope; print(modelscope.__version__)" 2>&1 | head -2
