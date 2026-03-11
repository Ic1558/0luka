#!/bin/zsh
set -euo pipefail

# Canonical bootstrap owner:
#   runtime/services/antigravity_bootstrap/bootstrap_contract.md
# Secret handling authority:
#   core/governance/secrets_policy.md

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
SCAN_RUNNER="$ROOT_DIR/runtime/services/antigravity_scan/runner.zsh"
REALTIME_RUNNER="$ROOT_DIR/runtime/services/antigravity_realtime/runner.zsh"
OBS_DIR="$ROOT_DIR/observability/logs/antigravity"
STATE_DIR="$ROOT_DIR/runtime/state/antigravity"
BOOTSTRAP_STATE="$STATE_DIR/bootstrap_state.json"

mkdir -p "$OBS_DIR" "$STATE_DIR"

python3 - <<'PY' "$BOOTSTRAP_STATE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
payload = {
    "service": "antigravity_bootstrap",
    "entrypoint_owner": "runtime/services/antigravity_bootstrap/pm2_start.zsh",
    "canonical_log_dir": "observability/logs/antigravity",
    "canonical_state_dir": "runtime/state/antigravity",
    "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
tmp_path = state_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(state_path)
PY

pm2 delete Antigravity-Monitor 2>/dev/null || true
pm2 delete OptionBugHunter 2>/dev/null || true

pm2 start "$SCAN_RUNNER" \
  --name "Antigravity-Monitor" \
  --output "$OBS_DIR/antigravity_monitor.out.log" \
  --error "$OBS_DIR/antigravity_monitor.err.log"
pm2 start "$REALTIME_RUNNER" \
  --name "OptionBugHunter" \
  --output "$OBS_DIR/option_bug_hunter.out.log" \
  --error "$OBS_DIR/option_bug_hunter.err.log"

pm2 save
pm2 list
