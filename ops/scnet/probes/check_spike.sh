#!/bin/bash
echo "=== spike1 进度 ==="
cat /public/home/acotxxttog/spike1_run3.log 2>/dev/null | grep -E "^\[S" | head -25
echo "=== 是否完成 ==="
ls -la /public/home/acotxxttog/aios-medic/experiments/spike1/results/ 2>/dev/null
