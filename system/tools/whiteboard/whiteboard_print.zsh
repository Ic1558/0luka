#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
WB_DIR="$ROOT/observability/whiteboard"

agent_id="${1:-}"
if [[ -z "$agent_id" ]]; then
  echo "usage: whiteboard_print.zsh <agent_id>" >&2
  exit 64
fi

f="$WB_DIR/${agent_id}.txt"
if [[ ! -f "$f" ]]; then
  echo "NO_BOARD: $f" >&2
  exit 66
fi

echo "===== WHITEBOARD: $agent_id ====="
cat "$f"
