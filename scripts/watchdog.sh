#!/usr/bin/env bash
# watchdog.sh — keeps backend and frontend alive
# Run in background: nohup bash scripts/watchdog.sh &
# Or via systemd (see bottom of file)

set -euo pipefail

PROJECT_DIR="/root/ia-investing"
BACKEND_PORT=8000
FRONTEND_PORT=3000
CHECK_INTERVAL=30

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

is_backend_up() {
    curl -sf -o /dev/null "http://localhost:${BACKEND_PORT}/api/v1/health" 2>/dev/null
}

is_frontend_up() {
    curl -sf -o /dev/null "http://localhost:${FRONTEND_PORT}" 2>/dev/null
}

start_backend() {
    log "Starting backend..."
    cd "$PROJECT_DIR"
    nohup uv run uvicorn apps.api.main:app \
        --host 0.0.0.0 --port "$BACKEND_PORT" \
        --reload --app-dir src \
        >> /root/ia-investing/logs/backend.log 2>&1 &
    log "Backend PID: $!"
}

start_frontend() {
    log "Starting frontend..."
    cd "$PROJECT_DIR/web"
    nohup npm run dev \
        >> /root/ia-investing/logs/frontend.log 2>&1 &
    log "Frontend PID: $!"
}

mkdir -p "$PROJECT_DIR/logs"

log "Watchdog started. Checking every ${CHECK_INTERVAL}s."

while true; do
    if ! is_backend_up; then
        log "Backend is DOWN — restarting..."
        start_backend
        sleep 10
    fi

    if ! is_frontend_up; then
        log "Frontend is DOWN — restarting..."
        start_frontend
        sleep 8
    fi

    sleep "$CHECK_INTERVAL"
done
