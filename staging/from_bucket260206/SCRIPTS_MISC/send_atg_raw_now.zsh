#!/usr/bin/env zsh
set -euo pipefail

CMD="$HOME/02luka/raycast/atg-snapshot.command"
if [[ ! -x "$CMD" ]]; then
  echo "❌ Missing or not executable: $CMD"
  exit 1
fi

# full = generate raw + copy raw to clipboard
"$CMD" full
