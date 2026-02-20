#!/usr/bin/env zsh
set -euo pipefail

# 0luka Summary Generator (SOT)
# Builds: reports/summary/latest.md

ROOT="${LUKA_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
TARGET="$ROOT/reports/summary/latest.md"
GENERATOR="tools/build_summary_min.zsh"
NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
NOW_LOCAL="$(date)"

# --- GUARD CHECK: Fail hard if target is not the canonical summary ---
if [[ "${TARGET:t}" != "latest.md" ]] || [[ "${TARGET:h:t}" != "summary" ]] || [[ "${TARGET:h:h:t}" != "reports" ]]; then
  echo "❌ FATAL: Safety lock. $0 must write to .../reports/summary/latest.md"
  echo "   Attempted: $TARGET"
  exit 1
fi

# Ensure directory exists
mkdir -p "$(dirname "$TARGET")"

TMP_TARGET="$TARGET.tmp"
STATUS_FILE="$ROOT/state/summary_last_status.json"

{
  echo "<!-- built_by=$GENERATOR timestamp=$NOW_UTC -->"
  echo "# 0luka — Summary"
  echo ""
  echo "- generated_local: $NOW_LOCAL"
  echo "- generated_utc: $NOW_UTC"
  echo "- generator: $GENERATOR"
  echo "- root: $ROOT"
  echo ""
  # ... [Existing signals and tails logic omitted for brevity in replace call, but included in final content] ...
  # (I will include the full block here to be safe as per tool rules)
  echo "## Signals"
  echo "### Recent incidents (if any)"
  INCIDENTS_DIR="$ROOT/observability/incidents"
  if [[ -d "$INCIDENTS_DIR" ]]; then
    ls -1t "$INCIDENTS_DIR" 2>/dev/null | head -n 5 | sed 's/^/- /' || echo "- (none)"
  else
    echo "- (dir missing: observability/incidents)"
  fi
  echo ""
  echo "### Latest open tasks"
  TASKS_DIR="$ROOT/artifacts/tasks/open"
  if [[ -d "$TASKS_DIR" ]]; then
    ls -1t "$TASKS_DIR" 2>/dev/null | head -n 5 | sed 's/^/- /' || echo "- (none)"
  else
    echo "- (dir missing: artifacts/tasks/open)"
  fi
  echo ""
  echo "## Log tails (current.log)"
  found_any=0
  for log_file in "$ROOT"/logs/components/*/current.log; do
    [[ -e "$log_file" ]] || continue
    found_any=1
    comp_name=$(basename "$(dirname "$log_file")")
    echo ""
    echo "### $comp_name"
    tail -n 30 "$log_file" | sed 's/^/    /'
  done
  if [[ "$found_any" -eq 0 ]]; then
    echo "- (no logs found under logs/components/*/current.log)"
  fi
} > "$TMP_TARGET"

# --- GUARD VALIDATION ---
FILE_SIZE=$(stat -f%z "$TMP_TARGET" 2>/dev/null || echo 0)
MIN_SIZE=1024 # 1KB

write_status() {
    local v_status=$1
    local detail=$2
    cat <<EOF > "$STATUS_FILE"
{
  "last_run_utc": "$NOW_UTC",
  "status": "$v_status",
  "detail": "$detail",
  "size_bytes": $FILE_SIZE
}
EOF
}

if [[ $FILE_SIZE -lt $MIN_SIZE ]]; then
  echo "⚠️ WARN: Quiet/Small Summary ($FILE_SIZE bytes < $MIN_SIZE bytes). Proceeding."
  write_status "warn" "size_small_quiet_repo"
else
  write_status "ok" "verified"
fi

# Atomic Move (Always update to reflect latest state, even if quiet)
mv "$TMP_TARGET" "$TARGET"
chmod 644 "$TARGET"

echo "✅ Wrote SOT Summary: $TARGET (Size: $FILE_SIZE)"
