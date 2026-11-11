#!/bin/bash
echo "=== main.html 原文 ==="
cat /tmp/main.html
echo; echo "=== 家目录 ==="
ls /public/home/acotxxttog/ | head -20
echo "=== dl_model.log ==="
head -20 /public/home/acotxxttog/dl_model.log 2>&1
echo "=== models 目录 ==="
ls -la /public/home/acotxxttog/models/ 2>&1
echo "=== 下载进程 ==="
ps aux | grep -i "modelscope\|download" | grep -v grep | head -5
echo "=== tail 诊断 ==="
type tail 2>&1 | head -3
