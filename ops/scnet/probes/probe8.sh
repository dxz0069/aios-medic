#!/bin/bash
echo "=== 等待解压(最多5分钟) ==="
for i in $(seq 1 15); do
  sleep 20
  RUNNING=$(pgrep -f "tar -xf.*proj4-devforge" | head -1)
  if [ -z "$RUNNING" ]; then echo "解压完成 t=$((i*20))s"; break; fi
  echo "t=$((i*20))s 解压中..."
done
echo "=== /root/proj4-devforge ==="
ls /root/proj4-devforge/ 2>/dev/null | head -15
echo "=== pyvenv.cfg ==="
cat /root/proj4-devforge/.venv/pyvenv.cfg 2>/dev/null
echo "=== venv pip list 关键包 ==="
/root/proj4-devforge/.venv/bin/pip list 2>/dev/null | grep -iE "^(aios|cerebrum|vllm|fastapi|uvicorn|transformers|torch|openai|pydantic)" | head -15
echo "=== import 测试 ==="
/root/proj4-devforge/.venv/bin/python -c "import cerebrum; print(\"cerebrum OK\", cerebrum.__file__)" 2>&1 | head -3
/root/proj4-devforge/.venv/bin/python -c "import aios; print(\"aios OK\")" 2>&1 | head -2
