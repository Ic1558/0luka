#!/usr/bin/env zsh
# Search MLS lessons by keyword and optional type.
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not installed" >&2
  echo "Install: brew install jq" >&2
  exit 1
fi

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
MLS_DB="${MLS_DB:-$ROOT/g/knowledge/mls_lessons.jsonl}"

usage() {
  cat <<'USAGE'
Usage: mls_search.zsh <keyword> [type]

Examples:
  mls_search.zsh sync
  mls_search.zsh "" solution
  mls_search.zsh merge failure
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

KEYWORD="$1"
TYPE="${2:-}"

if [[ ! -f "$MLS_DB" ]]; then
  echo "No MLS database found at $MLS_DB" >&2
  exit 1
fi

if [[ ! -s "$MLS_DB" ]]; then
  echo "No lessons found."
  exit 0
fi

RESULTS=$(python3 "$ROOT/system/tools/mls/mls_query.py" search --query "$KEYWORD" --format table --type "$TYPE" 2>/dev/null || true)

if [[ -z "$RESULTS" ]]; then
  echo "No lessons found."
  exit 0
fi

echo "$RESULTS"
