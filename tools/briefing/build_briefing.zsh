#!/usr/bin/env zsh
set -euo pipefail

# Root = repo root (script is inside tools/briefing/)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OBS="$ROOT/observability"

# Inputs (adjust if your actual folders differ)
TASKS_DIR="$OBS/tasks"
BRIDGE_INBOX="$OBS/bridge/inbox"
BRIDGE_INFLIGHT="$OBS/bridge/inflight"
DASH_PROGRESS="$OBS/dashboard/progress"
DASH_RESULTS="$OBS/dashboard/results"
REPORTS_DIR="$OBS/reports"
RETENTION_DIR="$OBS/retention/briefings"
QUARANTINE_DIR="$OBS/quarantine"

mkdir -p "$DASH_PROGRESS" "$RETENTION_DIR"

NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
STAMP="$(date -u +"%Y%m%d_%H%M")"
LATEST_MD="$DASH_PROGRESS/latest.md"
ARCHIVE_MD="$RETENTION_DIR/briefing_${STAMP}.md"

# Helper: count files safely (0 if missing)
count_files() {
  local d="$1"
  [[ -d "$d" ]] || { echo 0; return; }
  find "$d" -type f 2>/dev/null | wc -l | tr -d ' '
}

# Count task-ish things
TASK_JSON="$(count_files "$TASKS_DIR")"
INBOX_N="$(count_files "$BRIDGE_INBOX")"
INFLIGHT_N="$(count_files "$BRIDGE_INFLIGHT")"
RESULTS_N="$(count_files "$DASH_RESULTS")"
REPORTS_N="$(count_files "$REPORTS_DIR")"
RETENTION_N="$(count_files "$RETENTION_DIR")"
QUAR_N="$(count_files "$QUARANTINE_DIR")"

# Grab a few latest filenames for fast scan (not parsing content)
latest_list() {
  local d="$1" n="${2:-8}"
  [[ -d "$d" ]] || return 0
  ls -1t "$d" 2>/dev/null | head -n "$n" | sed 's/^/- /'
}

# Build markdown (simple + deterministic)
render_md() {
  cat <<MD
0luka Situation Briefing
- Generated: ${NOW_UTC}
- Root: ${ROOT}

Counts
- tasks: ${TASK_JSON}
- inbox: ${INBOX_N}
- inflight: ${INFLIGHT_N}
- results: ${RESULTS_N}
- reports: ${REPORTS_N}
- retention: ${RETENTION_N}
- quarantine: ${QUAR_N}

Latest items (filenames only)
Inbox:
$(latest_list "$BRIDGE_INBOX" 10)
Inflight:
$(latest_list "$BRIDGE_INFLIGHT" 10)
Results:
$(latest_list "$DASH_RESULTS" 10)
Reports:
$(latest_list "$REPORTS_DIR" 10)
Quarantine:
$(latest_list "$QUARANTINE_DIR" 10)

Pointers
- tasks: ${TASKS_DIR}
- inbox: ${BRIDGE_INBOX}
- inflight: ${BRIDGE_INFLIGHT}
- results: ${DASH_RESULTS}
- reports: ${REPORTS_DIR}
- progress: ${DASH_PROGRESS}
- retention: ${RETENTION_DIR}
- quarantine: ${QUARANTINE_DIR}
MD
}

TMP="$(mktemp)"
render_md > "$TMP"
cp "$TMP" "$LATEST_MD"
cp "$TMP" "$ARCHIVE_MD"
rm -f "$TMP"

echo "OK: wrote"
echo " - $LATEST_MD"
echo " - $ARCHIVE_MD"
