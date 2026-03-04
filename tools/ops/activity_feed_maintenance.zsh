#!/usr/bin/env zsh
set -euo pipefail
setopt NULL_GLOB

# Path setup
REPO_ROOT="/Users/icmini/0luka"
FEED_FILE="$REPO_ROOT/observability/logs/activity_feed.jsonl"
ARCHIVE_DIR="$REPO_ROOT/observability/logs/archive"
INDEX_FILE="$ARCHIVE_DIR/activity_feed.index.jsonl"
LOCK_DIR="$FEED_FILE.lock.d"
MAINT_LOG="$REPO_ROOT/observability/logs/maintenance_err.log"

mkdir -p "$ARCHIVE_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

# Lock/retry tuning (bounded wait to reduce contention)
LOCK_MAX_WAIT_MS=${LOCK_MAX_WAIT_MS:-1200}
LOCK_INITIAL_BACKOFF_MS=${LOCK_INITIAL_BACKOFF_MS:-20}
LOCK_MAX_BACKOFF_MS=${LOCK_MAX_BACKOFF_MS:-200}
LOCK_JITTER_MS=${LOCK_JITTER_MS:-30}
PYTHON_BIN=${PYTHON_BIN:-python3}

# Fail-closed error handling
function handle_error() {
    local err=$?
    local ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    # Write observability record
    echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"maintenance_failed\",\"exit_code\":$err}" >> "$MAINT_LOG"
    rm -rf "$LOCK_DIR"
    exit $err
}
trap handle_error ERR

# 1. Acquire Lock (bounded retry via atomic mkdir lockdir)
LOCK_ATTEMPTS=0
LOCK_WAIT_MS=0
LOCK_BACKOFF_MS=$LOCK_INITIAL_BACKOFF_MS
LOCK_START_NS=$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)

while true; do
  LOCK_ATTEMPTS=$((LOCK_ATTEMPTS + 1))
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo $$ > "$LOCK_DIR/pid" 2>/dev/null || true
    break
  fi

  LOCK_NOW_NS=$(python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
)
  LOCK_WAIT_MS=$(((LOCK_NOW_NS - LOCK_START_NS) / 1000000))

  if (( LOCK_WAIT_MS >= LOCK_MAX_WAIT_MS )); then
    echo "lock_acquired=false"
    echo "actions_taken=lock_contention"
    EVENT_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"ts\":\"$EVENT_TS\",\"level\":\"WARN\",\"source\":\"activity_feed_maintenance\",\"event\":\"lock_contention\",\"lock_dir\":\"$LOCK_DIR\",\"attempts\":$LOCK_ATTEMPTS,\"wait_ms\":$LOCK_WAIT_MS}" >> "$MAINT_LOG"
    exit 0
  fi

  JITTER=$(( RANDOM % (LOCK_JITTER_MS + 1) ))
  SLEEP_MS=$(( LOCK_BACKOFF_MS + JITTER ))
  sleep $(python3 - <<PY
ms=$SLEEP_MS
print(ms/1000.0)
PY
)

  LOCK_BACKOFF_MS=$(( LOCK_BACKOFF_MS * 2 ))
  if (( LOCK_BACKOFF_MS > LOCK_MAX_BACKOFF_MS )); then
    LOCK_BACKOFF_MS=$LOCK_MAX_BACKOFF_MS
  fi
done

trap 'rm -rf "$LOCK_DIR"' EXIT
echo "lock_acquired=true"

ACTIONS=()

# 2. Rotate (Threshold: 100KB)
MAX_BYTES=$((100 * 1024))
if [[ -f "$FEED_FILE" ]]; then
    
    # macOS stat
    SIZE=$(stat -f%z "$FEED_FILE" 2>/dev/null || stat -c%s "$FEED_FILE" 2>/dev/null || echo 0)
    
    if (( SIZE > MAX_BYTES )); then
        TS=$(date -u +"%Y%m%dT%H%M%SZ")
        ROTATED_FILE="$ARCHIVE_DIR/activity_feed.$TS.jsonl"
        mv "$FEED_FILE" "$ROTATED_FILE"
        touch "$FEED_FILE"
        ACTIONS+=("rotated")
        # Emit feed_rotated event (Pack 10: Index Sovereignty Contract)
        ROTATED_BASE=$(basename "$ROTATED_FILE")
        ROTATE_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "{\"ts_utc\":\"$ROTATE_TS\",\"action\":\"feed_rotated\",\"emit_mode\":\"runtime_auto\",\"old_path\":\"observability/logs/archive/$ROTATED_BASE\",\"new_path\":\"observability/logs/activity_feed.jsonl\",\"cutoff_offset\":$SIZE}" >> "$FEED_FILE"
    fi
fi

# 3. Prune (keep=5)
ARCHIVES=()
for f in "$ARCHIVE_DIR"/activity_feed.*.jsonl(N); do
    if [[ "$f" != *"index.jsonl"* ]]; then
        ARCHIVES+=("$f")
    fi
done
# Ensure sorted
ARCHIVES=("${(@o)ARCHIVES}")

if (( ${#ARCHIVES[@]} > 5 )); then
    TO_DELETE=$(( ${#ARCHIVES[@]} - 5 ))
    for (( i=1; i<=TO_DELETE; i++ )); do
        rm -f "${ARCHIVES[$i]}"
    done
    ACTIONS+=("pruned")
fi

# 4. Rebuild Index
if [[ ${#ACTIONS[@]} -gt 0 || ! -f "$INDEX_FILE" ]]; then
    # 4a. Rapid Structural Index (Zsh)
    : > "$INDEX_FILE.tmp"
    for arch in "$ARCHIVE_DIR"/activity_feed.*.jsonl(N); do
        if [[ "$arch" == *"index.jsonl"* ]]; then continue; fi
        FILE_TS=$(echo "$arch" | grep -o -E '[0-9]{8}T[0-9]{6}Z' || true)
        if [[ -n "$FILE_TS" ]]; then
            echo "{\"archive\":\"$(basename "$arch")\",\"ts\":\"$FILE_TS\"}" >> "$INDEX_FILE.tmp"
        fi
    done
    mv "$INDEX_FILE.tmp" "$INDEX_FILE"
    
    # 4b. Deep Trace Index (Python)
    EMIT_FLAG=""
    if [[ " ${ACTIONS[*]} " == *" rotated "* ]]; then EMIT_FLAG="--emit-event"; fi
    python3 "$REPO_ROOT/tools/ops/activity_feed_indexer.py" $EMIT_FLAG >> "$MAINT_LOG" 2>&1
    
    ACTIONS+=("indexed")
fi

if [[ ${#ACTIONS[@]} -eq 0 ]]; then
    ACTIONS+=("noop")
fi

echo "actions_taken=${ACTIONS[*]}"

# Emit event to activity feed
EVENT_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if [[ "${ACTIONS[*]}" == "noop" ]]; then
    RESULT="noop"
else
    RESULT=$(echo "${ACTIONS[*]}" | tr ' ' ',')
fi
echo "{\"ts_utc\":\"$EVENT_TS\",\"action\":\"activity_feed_maintenance\",\"emit_mode\":\"runtime_auto\",\"result\":\"$RESULT\",\"lock_acquired\":true,\"lock_dir\":\"$LOCK_DIR\",\"lock_attempts\":${LOCK_ATTEMPTS:-1},\"lock_wait_ms\":${LOCK_WAIT_MS:-0}}" >> "$FEED_FILE"
