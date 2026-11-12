#!/bin/bash
# ============================================================
# auth-server 的服务声明
#   由 template/supervisor.sh 统一启动/停止/记录日志
# ============================================================

SERVICE_NAMES=(api)
SERVICE_STOP_TIMEOUT=([api]=15)

start_api() {
    run_service api uvicorn main:app \
        --app-dir /data \
        --host "${UVICORN_HOST:-127.0.0.1}" \
        --port "${UVICORN_PORT:-8290}"
}
stop_api() { :; }
