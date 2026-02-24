#!/usr/bin/env zsh
set -euo pipefail

# Path setup
REPO_ROOT="/Users/icmini/0luka"
FEED_FILE="$REPO_ROOT/observability/logs/activity_feed.jsonl"
ARCHIVE_DIR="$REPO_ROOT/observability/logs/archive"
INDEX_FILE="$ARCHIVE_DIR/activity_feed.index.jsonl"
LOCK_FILE="$ARCHIVE_DIR/.rotation.lock"
MAINT_LOG="$REPO_ROOT/observability/logs/maintenance_err.log"

mkdir -p "$ARCHIVE_DIR"

# Fail-closed error handling
function handle_error() {
    local err=$?
    local ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    # Write observability record
    echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"maintenance_failed\",\"exit_code\":$err}" >> "$MAINT_LOG"
    rm -f "$LOCK_FILE"
    exit $err
}
trap handle_error ERR

# 1. Acquire Lock
if ! (set -o noclobber; echo $$ > "$LOCK_FILE") 2>/dev/null; then
    echo "lock_acquired=false"
    echo "actions_taken=lock_contention"
    EVENT_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"ts_utc\":\"$EVENT_TS\",\"action\":\"activity_feed_maintenance\",\"emit_mode\":\"runtime_auto\",\"result\":\"lock_contention\",\"lock_acquired\":false}" >> "$FEED_FILE"
    exit 0
fi
trap 'rm -f "$LOCK_FILE"' EXIT
echo "lock_acquired=true"

ACTIONS=()

# 2. Rotate (Threshold: 5MB)
MAX_BYTES=$((5 * 1024 * 1024))
if [[ -f "$FEED_FILE" ]]; then
    
    # macOS stat
    SIZE=$(stat -f%z "$FEED_FILE" 2>/dev/null || stat -c%s "$FEED_FILE" 2>/dev/null || echo 0)
    
    if (( SIZE > MAX_BYTES )); then
        TS=$(date -u +"%Y%m%dT%H%M%SZ")
        ROTATED_FILE="$ARCHIVE_DIR/activity_feed.$TS.jsonl"
        mv "$FEED_FILE" "$ROTATED_FILE"
        touch "$FEED_FILE"
        ACTIONS+=("rotated")
    fi
fi

# 3. Prune (keep=5)
ARCHIVES=($(ls -1 "$ARCHIVE_DIR"/activity_feed.*.jsonl 2>/dev/null | grep -v 'index.jsonl' | sort || true))
if (( ${#ARCHIVES[@]} > 5 )); then
    TO_DELETE=$(( ${#ARCHIVES[@]} - 5 ))
    for (( i=1; i<=TO_DELETE; i++ )); do
        rm -f "${ARCHIVES[$i]}"
    done
    ACTIONS+=("pruned")
fi

# 4. Rebuild Index
if [[ ${#ACTIONS[@]} -gt 0 || ! -f "$INDEX_FILE" ]]; then
    > "$INDEX_FILE.tmp"
    for arch in "$ARCHIVE_DIR"/activity_feed.*.jsonl; do
        if [[ "$arch" == *"index.jsonl"* ]]; then continue; fi
        FILE_TS=$(echo "$arch" | grep -o -E '[0-9]{8}T[0-9]{6}Z' || true)
        if [[ -n "$FILE_TS" ]]; then
            echo "{\"archive\":\"$(basename "$arch")\",\"ts\":\"$FILE_TS\"}" >> "$INDEX_FILE.tmp"
        fi
    done
    mv "$INDEX_FILE.tmp" "$INDEX_FILE"
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
echo "{\"ts_utc\":\"$EVENT_TS\",\"action\":\"activity_feed_maintenance\",\"emit_mode\":\"runtime_auto\",\"result\":\"$RESULT\",\"lock_acquired\":true}" >> "$FEED_FILE"
