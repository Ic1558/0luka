#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
APP_DIR="$ROOT_DIR/repos/option"
OBS_DIR="$ROOT_DIR/observability/logs/antigravity"
STATE_DIR="$ROOT_DIR/runtime/state/antigravity"
STATE_PATH="$STATE_DIR/antigravity_scan_runtime.json"

mkdir -p "$OBS_DIR" "$STATE_DIR"

if [ -e "$APP_DIR/logs" ] && [ ! -L "$APP_DIR/logs" ]; then
  rm -rf "$APP_DIR/logs"
fi
ln -sfn "$OBS_DIR" "$APP_DIR/logs"

python3 - <<'PY' "$STATE_PATH" "$OBS_DIR/antigravity.log"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
payload = {
    "service": "antigravity_scan",
    "entrypoint_owner": "runtime/services/antigravity_scan/runner.zsh",
    "delegated_implementation": "repos/option/src/antigravity_prod.py",
    "canonical_log_path": sys.argv[2],
    "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
tmp_path = state_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(state_path)
PY

cd "$APP_DIR"
exec dotenvx run -- ./venv/bin/python3 src/antigravity_prod.py
