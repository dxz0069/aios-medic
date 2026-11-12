#!/bin/bash
# 清理全部故障残留（脚本文件执行，避免嵌套引号把 pkill 模式弄脏）
pkill -9 -f "import multiprocessing as mp"
pkill -f leaky
pkill -f "signal.SIGKILL"
rm -f /run/medic/f0*.pid
sleep 1
echo "busy=$(pgrep -fc "import multiprocessing as mp" 2>/dev/null || echo 0) leaky=$(pgrep -fc leaky 2>/dev/null || echo 0) crasher=$(pgrep -fc "signal.SIGKILL" 2>/dev/null || echo 0)"
