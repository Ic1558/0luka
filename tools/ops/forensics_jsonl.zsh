#!/bin/zsh
# tools/ops/forensics_jsonl.zsh
# Audit-only forensics for finding broken lines in JSONL feed.

TARGET_LOG="${LUKA_ACTIVITY_FEED_JSONL:-observability/logs/activity_feed.jsonl}"

if [[ ! -f "$TARGET_LOG" ]]; then
    echo "❌ FATAL: Log file not found at $TARGET_LOG"
    exit 1
fi

echo "🔍 Analyzing: $TARGET_LOG"

python3 - <<'PY'
import json
import sys
import os

log_path = os.environ.get("LUKA_ACTIVITY_FEED_JSONL", "observability/logs/activity_feed.jsonl")

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            row = line.strip()
            if not row:
                continue
            try:
                json.loads(row)
            except Exception as e:
                print(f"❌ BAD LINE FOUND")
                print(f"Line Number: {i}")
                print(f"Exception:   {str(e)}")
                print(f"Content:     {row[:200]}...")
                sys.exit(2)
except FileNotFoundError:
    print(f"❌ File not found: {log_path}")
    sys.exit(1)

print("✅ Integrity Check: ALL LINES VALID JSON")
PY

EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
    exit 0
else
    exit $EXIT_CODE
fi
