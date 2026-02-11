#!/usr/bin/env zsh
set -euo pipefail
LOGDIR="$HOME/02luka/g/logs"
[[ -d "$LOGDIR" ]] || { echo "skip: $LOGDIR missing"; exit 0; }
TS="$(date +%Y%m%d_%H%M%S)"
DST="$HOME/02luka/_log_archives/$TS"
mkdir -p "$DST"
echo "== Archive noisy *.err.log to $DST =="
find "$LOGDIR" -name '*.err.log' -type f -maxdepth 1 | while read -r f; do
  sz="$(wc -c < "$f" | tr -d ' ')"
  echo "  $f  (${sz}B)"
  gzip -c "$f" > "$DST/$(basename "$f").gz"
  : > "$f"
done
echo "✅ Rotated. Old logs gzipped at $DST"
