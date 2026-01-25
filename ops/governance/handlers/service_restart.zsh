#!/bin/zsh
# 0luka Service Restart Handler v1.0
# Targeted for: opal-api

LUKA_SOT="/Users/icmini/0luka"
APP_DIR="$LUKA_SOT/runtime/apps/opal_api"
VENV_BIN="$LUKA_SOT/runtime/venv/opal/bin"
LOG_DIR="$LUKA_SOT/observability/logs"

echo "[OPAL RESTART] Starting..."

# 1. Kill existing uvicorn on port 7001
PID=$(lsof -ti:7001)
if [ ! -z "$PID" ]; then
    echo "[OPAL RESTART] Killing existing PID $PID"
    kill -9 $PID
fi

# 2. Start from venv
export LUKA_SOT="$LUKA_SOT"
export PYTHONPATH="$LUKA_SOT:$APP_DIR"

cd "$APP_DIR"
nohup $VENV_BIN/python -m uvicorn opal_api_server:app --host 0.0.0.0 --port 7001 > "$LOG_DIR/opal_api_restart.log" 2>&1 &

# 3. Wait for port
sleep 3
if lsof -i:7001 > /dev/null; then
    echo "[OPAL RESTART] SUCCESS: Port 7001 is up"
    exit 0
else
    echo "[OPAL RESTART] FAILURE: Port 7001 down"
    exit 1
fi
