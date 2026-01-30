#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
WB_DIR="$ROOT/observability/whiteboard"
f="$WB_DIR/last_snapshot_pointer.txt"
if [[ -f "$f" ]]; then
  cat "$f"
else
  echo "N/A"
fi
