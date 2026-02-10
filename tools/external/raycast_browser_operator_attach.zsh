#!/bin/zsh
# @raycast.schemaVersion 1
# @raycast.title Browser Operator: Attach My Chrome (Confirm)
# @raycast.mode silent
# @raycast.needsConfirmation true
# @raycast.description Enqueue a browser operator task that attaches to a debug Chrome instance.
# @raycast.argument1 { "type": "text", "placeholder": "[{\"action\":\"open_url\",\"url\":\"https://example.com\"}]" }
# @raycast.argument2 { "type": "text", "optional": true, "placeholder": "allow_hosts (comma-separated)" }

set -euo pipefail

steps_json="${1:-}"
allow_hosts_csv="${2:-}"

if [[ -z "$steps_json" ]]; then
  echo "Steps JSON is required."
  exit 1
fi

root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
inbox_dir="$root_dir/observability/bridge/inbox/browser_op"
mkdir -p "$inbox_dir"

task_id="browser_op_$(date -u +%Y%m%dT%H%M%SZ)_$RANDOM"
export STEPS_JSON="$steps_json"
export ALLOW_HOSTS="$allow_hosts_csv"
export TASK_ID="$task_id"
export OUT_PATH="$inbox_dir/$task_id.json"

python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

steps_json = os.environ["STEPS_JSON"]
allow_hosts_csv = os.environ.get("ALLOW_HOSTS", "")

def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

try:
    steps = json.loads(steps_json)
except json.JSONDecodeError as exc:
    print(f"Invalid steps JSON: {exc}")
    sys.exit(1)

if not isinstance(steps, list):
    print("Steps JSON must be a list.")
    sys.exit(1)

constraints = {"allow_https_only": True}
if allow_hosts_csv:
    constraints["allow_hosts"] = [host.strip() for host in allow_hosts_csv.split(",") if host.strip()]

payload = {
    "task_id": os.environ["TASK_ID"],
    "ts": utc_ts(),
    "mode": "attach_user_chrome",
    "steps": steps,
    "constraints": constraints,
}

out_path = os.environ["OUT_PATH"]
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")

print(f"Enqueued {out_path}")
PY
