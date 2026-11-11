#!/bin/bash
source /public/home/acotxxttog/.ai_user_info/ai_proxy 2>/dev/null
echo "=== sourcefind main ==="
timeout 25 curl -sk https://download.sourcefind.cn:65024/4/main/ -o /tmp/main.html -w "http=%{http_code} size=%{size_download}\n"
grep -oE "href=\"[^\"]+\"" /tmp/main.html 2>/dev/null | sed "s/href=//g;s/\"//g" | grep -viE "css|js|png|ico" | head -25
echo "=== 模型进度 ==="
/usr/bin/tail -n 2 /public/home/acotxxttog/dl_model.log 2>/dev/null || true
du -sh /public/home/acotxxttog/models/Qwen2.5-7B-Instruct 2>/dev/null || echo "模型目录未创建"
