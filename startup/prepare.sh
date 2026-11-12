#!/bin/bash
# ============================================================
# 启动前的准备：每次启动容器都执行（docker restart 也会执行）
#   - 把镜像里的应用代码和前端产物同步到数据目录 /data
#   - 前端是构建产物（文件名带哈希）：每次清空重铺
# ============================================================
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/log.sh"

SRC_DIR=/opt/sso-auth
DATA_DIR=/data

mkdir -p "$DATA_DIR"
cp "$SRC_DIR/main.py" "$DATA_DIR/main.py"

rm -rf "$DATA_DIR/static"
mkdir -p "$DATA_DIR/static"
cp -r "$SRC_DIR/static/." "$DATA_DIR/static/"
chmod -R a+rX "$DATA_DIR/static"

log info "应用文件已同步到 ${DATA_DIR}"
