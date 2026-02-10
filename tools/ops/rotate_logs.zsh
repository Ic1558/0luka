#!/usr/bin/env zsh
# rotate_logs.zsh — Atomic log rotation for 0luka
# Targets: observability/, artifacts/ (generated logs only)
# Safe: excludes evidence/, sot/, and other SOT directories

set -euo pipefail

ROOT="${1:-$PWD}"
KEEP_DAYS="${KEEP_DAYS:-14}"

# Only rotate generated logs, never touch long-lived evidence/SOT
TARGETS=(
  "$ROOT/observability"
  "$ROOT/artifacts"
)

# Exclude patterns (protected dirs)
EXCLUDES=(
  "$ROOT/observability/evidence"
  "$ROOT/observability/sot"
  "$ROOT/observability/schemas"
  "$ROOT/observability/runbooks"
  "$ROOT/artifacts/sot"
)

is_excluded() {
  local p="$1"
  for ex in "${EXCLUDES[@]}"; do
    [[ "$p" == "$ex"* ]] && return 0
  done
  return 1
}

compress_count=0
delete_count=0

for d in "${TARGETS[@]}"; do
  [[ -d "$d" ]] || continue

  # Compress logs older than 1 day
  find "$d" -type f \( -name "*.log" -o -name "*.jsonl" -o -name "*.ndjson" -o -name "*.stdout.log" -o -name "*.stderr.log" \) -mtime +1 -print0 2>/dev/null \
  | while IFS= read -r -d '' f; do
      if is_excluded "$f"; then
        continue
      fi
      if [[ ! -f "$f.gz" ]]; then
        gzip -9 "$f" && ((compress_count++)) || true
      fi
    done

  # Delete compressed files older than KEEP_DAYS
  find "$d" -type f -name "*.gz" -mtime +"$KEEP_DAYS" -print0 2>/dev/null \
  | while IFS= read -r -d '' gz; do
      if is_excluded "$gz"; then
        continue
      fi
      rm -f "$gz" && ((delete_count++)) || true
    done
done

echo "✅ rotate_logs.zsh complete"
echo "   Targets: ${TARGETS[*]}"
echo "   KEEP_DAYS=$KEEP_DAYS"
echo "   Compressed: $compress_count files"
echo "   Deleted: $delete_count old .gz files"
