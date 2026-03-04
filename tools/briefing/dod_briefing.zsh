#!/usr/bin/env zsh
set -euo pipefail
REPO="${REPO:-/Users/icmini/0luka}"
FILE="$REPO/tools/briefing/DOD_BRIEFING.md"

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: missing $FILE"
  exit 2
fi

echo "== DoD/PPR Briefing =="
cat "$FILE"

if command -v pbcopy >/dev/null 2>&1; then
  cat "$FILE" | pbcopy
  echo
  echo "(copied to clipboard)"
fi
