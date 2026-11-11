#!/usr/bin/env bash
# 启动一次性 Medic 实验沙箱。
#   --cap-add NET_ADMIN : F05 故障（tc netem）所需
#   --tmpfs /var/scratch: F02 磁盘写满的受控目标（不触碰根文件系统）
#   -p 8080              : 玩具服务健康端口映射到宿主机 18080
set -euo pipefail

NAME=medic-sandbox
IMAGE=medic-sandbox

if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
    echo "容器 ${NAME} 已存在，先删除旧实例"
    docker rm -f "${NAME}" >/dev/null
fi

docker run -d --name "${NAME}" \
    --cap-add NET_ADMIN \
    --memory 2g \
    --tmpfs /var/scratch:size=300m \
    -p 18080:8080 \
    "${IMAGE}"

echo "沙箱已启动: docker exec -it ${NAME} bash  |  服务健康检查: curl http://127.0.0.1:18080/health"
