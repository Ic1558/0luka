import os
import sys
import json
from pathlib import Path

os.environ["LUKA_RUNTIME_ROOT"] = "/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.mmllICcNbq"

from core.activity_feed_guard import guarded_append_activity_feed, SCHEMA_PATH

# Create a minimal valid schema for testing if real one is complex
SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
SCHEMA_PATH.write_text(json.dumps({
    "type": "object",
    "required": ["ts_utc", "action"],
    "properties": {
        "ts_utc": {"type": "string"},
        "action": {"type": "string"}
    }
}))

# 1. Invalid payload (missing required field 'action')
bad_payload = {
    "ts_utc": "2026-03-04T00:00:00Z"
}

# This should return False because it fails closed on invalid data
append_ok = guarded_append_activity_feed(Path("dummy"), bad_payload)
print(f"APPEND_INVALID_OK: {append_ok}")

# Verify violation log
violation_log = Path("/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.mmllICcNbq/logs/feed_guard_violations.jsonl")
if violation_log.exists():
    last_violation = json.loads(violation_log.read_text().splitlines()[-1])
    print(f"VIOLATION_REASON: {last_violation['reason']}")

# Verify feed lines (Only Anchor should be there = 1)
feed_file = Path("/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.mmllICcNbq/logs/activity_feed.jsonl")
lines = feed_file.read_text().splitlines()
print(f"FEED_LINES: {len(lines)}")
