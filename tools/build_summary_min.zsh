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

{
  echo "<!-- built_by=$GENERATOR timestamp=$NOW_UTC -->"
  echo "# 0luka — Summary"
  echo ""
  echo "- generated_local: $NOW_LOCAL"
  echo "- generated_utc: $NOW_UTC"
  echo "- generator: $GENERATOR"
  echo "- root: $ROOT"
  echo ""

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

} > "$TARGET"

echo "✅ Wrote SOT Summary: $TARGET"
