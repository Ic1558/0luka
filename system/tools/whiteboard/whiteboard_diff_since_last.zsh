#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
WB_DIR="$ROOT/observability/whiteboard"

agent_id="${1:-}"
if [[ -z "$agent_id" ]]; then
  echo "usage: whiteboard_diff_since_last.zsh <agent_id>" >&2
  exit 64
fi

curr="$WB_DIR/${agent_id}.txt"
prev="$WB_DIR/${agent_id}.prev.txt"

if [[ ! -f "$curr" ]]; then
  echo "NO_BOARD: $curr" >&2
  exit 66
fi

# If no prev, create it and print nothing
if [[ ! -f "$prev" ]]; then
  cp -f "$curr" "$prev"
  echo "NO_DIFF_BASELINE: created ${agent_id}.prev.txt"
  exit 0
fi

echo "===== DIFF: $agent_id (prev -> curr) ====="
# diff may exit 1 when different; don't fail the script
diff -u "$prev" "$curr" || true

# rotate baseline to current for next diff
cp -f "$curr" "$prev"
