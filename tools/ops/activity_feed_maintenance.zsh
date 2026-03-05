#!/usr/bin/env zsh
set -euo pipefail
setopt NULL_GLOB

# Path setup
REPO_ROOT="/Users/icmini/0luka"
RUNTIME_ROOT="${LUKA_RUNTIME_ROOT:-/Users/icmini/0luka_runtime}"
FEED_FILE="$RUNTIME_ROOT/logs/activity_feed.jsonl"
ARCHIVE_DIR="$RUNTIME_ROOT/logs/archive"
INDEX_FILE="$ARCHIVE_DIR/activity_feed.index.jsonl"
SEALS_FILE="$RUNTIME_ROOT/logs/rotation_seals.jsonl"
REGISTRY_APPEND_HELPER="$REPO_ROOT/tools/ops/rotation_registry_append.py"
EPOCH_EMITTER_HELPER="$REPO_ROOT/tools/ops/epoch_emitter.py"
LOCK_DIR="$ARCHIVE_DIR/.rotation.lock.d"
MAINT_LOG="$RUNTIME_ROOT/logs/maintenance_err.log"
APPEND_HELPER="$REPO_ROOT/tools/ops/activity_feed_append.py"

mkdir -p "$ARCHIVE_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"
mkdir -p "$(dirname "$SEALS_FILE")"

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

function emit_feed_event() {
    local payload="$1"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if [[ ! -f "$APPEND_HELPER" ]]; then
        echo "{\"ts\":\"$ts\",\"level\":\"WARN\",\"source\":\"activity_feed_maintenance\",\"event\":\"append_helper_missing\",\"path\":\"$APPEND_HELPER\"}" >> "$MAINT_LOG"
        return 0
    fi
    "$PYTHON_BIN" "$APPEND_HELPER" --feed "$FEED_FILE" --json "$payload" >/dev/null 2>>"$MAINT_LOG" || true
}

function emit_rotation_seal() {
    local segment_path="$1"
    local seals_path="$2"
    local seal_ts
    seal_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if ! "$PYTHON_BIN" - "$segment_path" "$seals_path" "$seal_ts" 2>>"$MAINT_LOG" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

segment_path = Path(sys.argv[1])
seals_path = Path(sys.argv[2])
sealed_at_utc = sys.argv[3]

segment_name = segment_path.name
first_hash = None
last_hash = None
line_count = 0

with segment_path.open("r", encoding="utf-8", errors="replace") as f:
    for line_no, raw in enumerate(f, start=1):
        s = raw.strip()
        if not s:
            continue
        line_count += 1
        try:
            row = json.loads(s)
        except Exception:
            raise SystemExit(2)
        if not isinstance(row, dict):
            raise SystemExit(2)
        h = row.get("hash")
        if not isinstance(h, str) or not h:
            raise SystemExit(3)
        if first_hash is None:
            first_hash = h
        last_hash = h

if not first_hash or not last_hash or line_count <= 0:
    raise SystemExit(3)

seal_input = f"{segment_name}{first_hash}{last_hash}{line_count}".encode("utf-8")
seal_hash = hashlib.sha256(seal_input).hexdigest()
record = {
    "action": "rotation_seal",
    "segment_name": segment_name,
    "first_hash": first_hash,
    "last_hash": last_hash,
    "line_count": line_count,
    "sealed_at_utc": sealed_at_utc,
    "seal_hash": seal_hash,
}
seals_path.parent.mkdir(parents=True, exist_ok=True)
with seals_path.open("a", encoding="utf-8") as out:
    out.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    out.flush()
    os.fsync(out.fileno())

print(
    "|".join(
        [
            segment_name,
            seal_hash,
            first_hash,
            last_hash,
            str(line_count),
            sealed_at_utc,
        ]
    )
)
PY
    then
        return 1
    fi
    return 0
}

function emit_rotation_registry() {
    local segment_name="$1"
    local seal_hash="$2"
    local first_hash="$3"
    local last_hash="$4"
    local line_count="$5"
    local sealed_at_utc="$6"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    if [[ ! -f "$REGISTRY_APPEND_HELPER" ]]; then
        echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"rotation_registry_helper_missing\",\"path\":\"$REGISTRY_APPEND_HELPER\"}" >> "$MAINT_LOG"
        return 1
    fi

    if ! "$PYTHON_BIN" "$REGISTRY_APPEND_HELPER" \
        "$segment_name" \
        "$seal_hash" \
        "$first_hash" \
        "$last_hash" \
        "$line_count" \
        "$sealed_at_utc" \
        --json >>"$MAINT_LOG" 2>&1; then
        echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"rotation_registry_append_failed\",\"segment\":\"$segment_name\"}" >> "$MAINT_LOG"
        return 1
    fi

    return 0
}

function emit_epoch() {
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if [[ ! -f "$EPOCH_EMITTER_HELPER" ]]; then
        echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"epoch_emitter_helper_missing\",\"path\":\"$EPOCH_EMITTER_HELPER\"}" >> "$MAINT_LOG"
        return 1
    fi
    if ! "$PYTHON_BIN" "$EPOCH_EMITTER_HELPER" --runtime-root "$RUNTIME_ROOT" --json >>"$MAINT_LOG" 2>&1; then
        echo "{\"ts\":\"$ts\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"epoch_emit_failed\"}" >> "$MAINT_LOG"
        return 1
    fi
    return 0
}

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
        if SEAL_META="$(emit_rotation_seal "$ROTATED_FILE" "$SEALS_FILE")"; then
            ACTIONS+=("sealed")
            IFS='|' read -r REG_SEGMENT REG_SEAL_HASH REG_FIRST_HASH REG_LAST_HASH REG_LINE_COUNT REG_SEALED_AT_UTC <<< "$SEAL_META"
            if emit_rotation_registry \
                "$REG_SEGMENT" \
                "$REG_SEAL_HASH" \
                "$REG_FIRST_HASH" \
                "$REG_LAST_HASH" \
                "$REG_LINE_COUNT" \
                "$REG_SEALED_AT_UTC"; then
                ACTIONS+=("registered")
            else
                ACTIONS+=("registry_failed")
            fi
        else
            ACTIONS+=("seal_failed")
            SEAL_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
            echo "{\"ts\":\"$SEAL_TS\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"rotation_seal_failed\",\"segment\":\"$(basename "$ROTATED_FILE")\"}" >> "$MAINT_LOG"
        fi
        # Emit feed_rotated event (Pack 10: Index Sovereignty Contract)
        ROTATED_BASE=$(basename "$ROTATED_FILE")
        ROTATE_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        ROTATE_PAYLOAD="{\"ts_utc\":\"$ROTATE_TS\",\"action\":\"feed_rotated\",\"emit_mode\":\"runtime_auto\",\"old_path\":\"runtime/logs/archive/$ROTATED_BASE\",\"new_path\":\"runtime/logs/activity_feed.jsonl\",\"cutoff_offset\":$SIZE}"
        emit_feed_event "$ROTATE_PAYLOAD"
        if [[ " ${ACTIONS[*]} " == *" sealed "* ]]; then
            if emit_epoch; then
                ACTIONS+=("epoch_emitted")
            else
                ACTIONS+=("epoch_failed")
            fi
        fi
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
    if ! "$PYTHON_BIN" "$REPO_ROOT/tools/ops/activity_feed_indexer.py" $EMIT_FLAG >> "$MAINT_LOG" 2>&1; then
        IDX_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "{\"ts\":\"$IDX_TS\",\"level\":\"ERROR\",\"source\":\"activity_feed_maintenance\",\"event\":\"index_rebuild_failed\"}" >> "$MAINT_LOG"
        ACTIONS+=("index_failed")
    fi
    
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
MAINT_PAYLOAD="{\"ts_utc\":\"$EVENT_TS\",\"action\":\"activity_feed_maintenance\",\"emit_mode\":\"runtime_auto\",\"result\":\"$RESULT\",\"lock_acquired\":true,\"lock_dir\":\"$LOCK_DIR\",\"lock_attempts\":${LOCK_ATTEMPTS:-1},\"lock_wait_ms\":${LOCK_WAIT_MS:-0}}"
emit_feed_event "$MAINT_PAYLOAD"
