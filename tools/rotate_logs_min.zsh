#!/usr/bin/env zsh
set -euo pipefail

ROOT="${1:-$PWD}"
cd "$ROOT"

RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMP_DIR="logs/components"

if [[ ! -d "$COMP_DIR" ]]; then
  echo "ERROR: missing $COMP_DIR" >&2
  exit 1
fi

today="$(date +%Y%m%d)"
now_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

for d in "$COMP_DIR"/*; do
  [[ -d "$d" ]] || continue
  comp="$(basename "$d")"
  cur="$d/current.log"
  daily="$d/${today}.log"

  # Ensure files exist
  : > "$cur" 2>/dev/null || true
  : > "$daily" 2>/dev/null || true

  # Append current -> daily, then truncate current
  if [[ -s "$cur" ]]; then
    {
      echo "---- ROTATE @ ${now_ts} (append current -> ${today}.log) ----"
      cat "$cur"
      echo ""
    } >> "$daily"
    : > "$cur"
  fi

  # Compress older than today (skip already gz)
  for f in "$d"/*.log(.N); do
    [[ "$(basename "$f")" == "${today}.log" ]] && continue
    [[ "$f" == *.gz ]] && continue
    gzip -f "$f" || true
  done

  # Retain N days (both .log.gz and .log)
  # macOS find: -mtime +N means strictly older than N*24h
  find "$d" -type f \( -name "*.log" -o -name "*.log.gz" \) -mtime "+$RETENTION_DAYS" -print -delete 2>/dev/null || true
done

echo "OK: rotation done (retention=${RETENTION_DAYS}d)"
