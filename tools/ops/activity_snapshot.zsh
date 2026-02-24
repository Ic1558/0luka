#!/usr/bin/env zsh
# tools/ops/activity_snapshot.zsh — Forensic Activity Feed Snapshot Generator
# Extracts bounded segments of the activity feed for proof packs.

set -euo pipefail

REPO_ROOT="/Users/icmini/0luka"
FEED_FILE="$REPO_ROOT/observability/logs/activity_feed.jsonl"
SNAPSHOT_DIR="$REPO_ROOT/observability/artifacts/proof_packs"

usage() {
    echo "Usage: $0 --run-id <id> [--output-dir <path>]"
    echo "       $0 --from <iso-ts> --to <iso-ts>"
    exit 1
}

RUN_ID=""
FROM_TS=""
TO_TS=""
OUT_DIR="$SNAPSHOT_DIR"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-id) RUN_ID="$2"; shift 2 ;;
        --from) FROM_TS="$2"; shift 2 ;;
        --to) TO_TS="$2"; shift 2 ;;
        --output-dir) OUT_DIR="$2"; shift 2 ;;
        *) usage ;;
    esac
done

mkdir -p "$OUT_DIR"

# 1. Filter
TS_SUFFIX=$(date -u +"%Y%m%dT%H%M%SZ")
SNAPSHOT_FILE="$OUT_DIR/activity_$TS_SUFFIX.snapshot.jsonl"

if [[ -n "$RUN_ID" ]]; then
    grep "$RUN_ID" "$FEED_FILE" > "$SNAPSHOT_FILE" || { echo "Error: Run ID $RUN_ID not found in feed."; exit 1; }
elif [[ -n "$FROM_TS" && -n "$TO_TS" ]]; then
    # Simple lexical grep for timestamps (ISO 8601 allows string comparison)
    # This is a approximation, but works given the append-only nature
    awk -v from="$FROM_TS" -v to="$TO_TS" '
        match($0, /"ts_utc":"([^"]+)"/, m) {
            if (m[1] >= from && m[1] <= to) print $0
        }
    ' "$FEED_FILE" > "$SNAPSHOT_FILE"
else
    usage
fi

# 2. Verify Result
if [[ ! -s "$SNAPSHOT_FILE" ]]; then
    echo "Error: Resulting snapshot is empty."
    rm -f "$SNAPSHOT_FILE"
    exit 1
fi

# 3. Hash
SHA_FILE="$SNAPSHOT_FILE.sha256"
shasum -a 256 "$SNAPSHOT_FILE" | cut -d' ' -f1 > "$SHA_FILE"

echo "Snapshot created: $SNAPSHOT_FILE"
echo "Hash: $(cat "$SHA_FILE")"
echo "exit_code=0"
