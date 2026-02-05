#!/usr/bin/env zsh
set -euo pipefail

# Moves the latest /export markdown into cole/session_log.
#
# Usage:
#   zsh cole/tools/adopt_export.zsh
#   zsh cole/tools/adopt_export.zsh /path/to/export.md

HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"

DEST_DIR="$ROOT/cole/session_log"
mkdir -p "$DEST_DIR"

SRC=""
if [[ $# -ge 1 ]]; then
  SRC="$1"
else
  candidates=()
  for f in "$ROOT"/cole-session-ses_*.md "$ROOT"/session-ses_*.md; do
    if [[ -f "$f" ]]; then
      candidates+=("$f")
    fi
  done

  if (( ${#candidates[@]} == 0 )); then
    print -u2 "No export files found in: $ROOT"
    print -u2 "Expected something like: cole-session-ses_XXXX.md"
    exit 1
  fi

  SRC="$(ls -t "${candidates[@]}" | head -n 1)"
fi

if [[ ! -f "$SRC" ]]; then
  print -u2 "Not a file: $SRC"
  exit 1
fi

BASE="$(basename "$SRC")"
DEST="$DEST_DIR/$BASE"

if [[ -e "$DEST" ]]; then
  TS="$(date -u +"%Y%m%dT%H%M%SZ")"
  DEST="$DEST_DIR/${BASE%.md}_${TS}.md"
fi

mv "$SRC" "$DEST"
print "$DEST"
