#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
WB_DIR="$ROOT/observability/whiteboard"
TOOLS_DIR="$ROOT/system/tools/whiteboard"
mkdir -p "$WB_DIR"

agent_id="${1:-}"
title="${2:-}"
if [[ -z "$agent_id" || -z "$title" ]]; then
  # Silent exit on missing args to avoid breaking pipes, or log to stderr
  exit 64
fi

out_txt="$WB_DIR/${agent_id}.txt"
out_json="$WB_DIR/${agent_id}.json"
lockdir="$WB_DIR/.lock.${agent_id}"

# Acquire lock (atomic)
for _ in {1..200}; do
  if mkdir "$lockdir" 2>/dev/null; then
    break
  fi
  sleep 0.05
done
if [[ ! -d "$lockdir" ]]; then
  exit 73
fi
cleanup() { rmdir "$lockdir" >/dev/null 2>&1 || true }
trap cleanup EXIT

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

tmp_txt="$(mktemp "$WB_DIR/.${agent_id}.txt.XXXXXX")"
tmp_json="$(mktemp "$WB_DIR/.${agent_id}.json.XXXXXX")"

# Read body from stdin
body="$(cat)"

# Write TXT (overwrite)
{
  echo "0luka whiteboard"
  echo "agent_id: $agent_id"
  echo "ts: $ts"
  echo "title: $title"
  echo "----"
  echo "$body"
  echo
  echo "pointers:"
  echo "- last_snapshot: $(cat "$WB_DIR/pointers/last_snapshot.txt" 2>/dev/null || echo "N/A")"
  echo "- last_action:   $(cat "$WB_DIR/pointers/last_action.txt" 2>/dev/null || echo "N/A")"
} > "$tmp_txt"

# Write JSON (overwrite) — robust python heredoc
python3 - <<PY > "$tmp_json"
import json, os, sys
root = os.environ.get("ROOT", os.path.expanduser("~/0luka"))
wb_dir = os.path.join(root, "observability", "whiteboard")

# Safe argument handling
agent_id = r'''${agent_id}'''
title = r'''${title}'''
ts = r'''${ts}'''
body = r'''${body}'''

def readf(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "N/A"

obj = {
    "schema_version": "whiteboard.v1",
    "agent_id": agent_id,
    "ts": ts,
    "title": title,
    "body": body,
    "pointers": {
        "last_snapshot": readf(os.path.join(wb_dir, "pointers", "last_snapshot.txt")),
        "last_action": readf(os.path.join(wb_dir, "pointers", "last_action.txt")),
    }
}
print(json.dumps(obj, ensure_ascii=False, indent=2))
PY

# Atomic replace
mv -f "$tmp_txt" "$out_txt"
mv -f "$tmp_json" "$out_json"

exit 0
