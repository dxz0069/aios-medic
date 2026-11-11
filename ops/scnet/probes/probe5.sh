#!/bin/bash
source /public/home/acotxxttog/.ai_user_info/ai_proxy 2>/dev/null
echo "=== proj4-reqs/third_party ==="
find /public/home/acotxxttog/proj4-reqs -maxdepth 3 2>/dev/null | head -20
echo; echo "=== 重启模型下载 ==="
mkdir -p /public/home/acotxxttog/models
cd /public/home/acotxxttog
setsid nohup python3 -m modelscope download --model Qwen/Qwen2.5-7B-Instruct --local_dir /public/home/acotxxttog/models/Qwen2.5-7B-Instruct > /public/home/acotxxttog/dl_model2.log 2>&1 < /dev/null &
sleep 20
echo "--- 20秒后日志 ---"; head -8 dl_model2.log; du -sh models/Qwen2.5-7B-Instruct 2>/dev/null
echo; echo "=== z-file API 探测 ==="
for u in "https://download.sourcefind.cn:65024/api/storage/list?path=%2F4%2Fmain&currentPage=1&pageSize=50" "https://download.sourcefind.cn:65024/api/site/storage/list" "https://download.sourcefind.cn:65024/api/admin/storage/list"; do
  echo "--- $u"; timeout 15 curl -sk "$u" -w " [http=%{http_code}]" | head -c 300; echo
done
