#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
APP_DIR="$ROOT_DIR/repos/option"
OBS_DIR="$ROOT_DIR/observability/logs/antigravity"
STATE_DIR="$ROOT_DIR/runtime/state/antigravity"
STATE_PATH="$STATE_DIR/antigravity_realtime_runtime.json"

mkdir -p "$OBS_DIR" "$STATE_DIR"

if [ -e "$APP_DIR/logs" ] && [ ! -L "$APP_DIR/logs" ]; then
  rm -rf "$APP_DIR/logs"
fi
ln -sfn "$OBS_DIR" "$APP_DIR/logs"

python3 - <<'PY' "$STATE_PATH" "$OBS_DIR/option_bug_hunter.out.log" "$OBS_DIR/option_bug_hunter.err.log"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
payload = {
    "service": "antigravity_realtime",
    "entrypoint_owner": "runtime/services/antigravity_realtime/runner.zsh",
    "delegated_implementation": "repos/option/src/live.js",
    "canonical_stdout_path": sys.argv[2],
    "canonical_stderr_path": sys.argv[3],
    "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
tmp_path = state_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(state_path)
PY

cd "$APP_DIR"
exec dotenvx run -- node src/live.js
