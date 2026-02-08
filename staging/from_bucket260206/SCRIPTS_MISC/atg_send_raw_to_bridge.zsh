#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/02luka"
RAY="$ROOT/raycast"
cmd="$RAY/atg-snapshot-raw.command"

if [[ ! -x "$cmd" ]]; then
  echo "ERROR: missing or not executable: $cmd"
  exit 1
fi

"$cmd" >/dev/null
echo "OK: RAW dropped → $ROOT/magic_bridge/inbox/atg_snapshot.md (and copied to clipboard)"
