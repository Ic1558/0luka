import os
import sys
import json
from pathlib import Path

# Mock RUNTIME_ROOT in core.config before importing guard
os.environ["LUKA_RUNTIME_ROOT"] = "/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.rObL87bXad"

from core.activity_feed_guard import guarded_append_activity_feed, SCHEMA_PATH

# 1. Simulate Schema Missing (point to non-existent path)
import core.activity_feed_guard
core.activity_feed_guard.SCHEMA_PATH = Path("/tmp/non_existent_schema.json")

payload = {
    "ts_utc": "2026-03-04T00:00:00Z",
    "action": "test_fail_open",
    "emit_mode": "manual_test"
}

# This should return True because it fails open
append_ok = guarded_append_activity_feed(Path("dummy"), payload)
print(f"APPEND_UNAVAILABLE_OK: {append_ok}")

# Verify violation log
violation_log = Path("/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.rObL87bXad/logs/feed_guard_violations.jsonl")
if violation_log.exists():
    last_violation = json.loads(violation_log.read_text().splitlines()[-1])
    print(f"VIOLATION_REASON: {last_violation['reason']}")

# Verify feed lines (Anchor + our payload = 2)
feed_file = Path("/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.rObL87bXad/logs/activity_feed.jsonl")
lines = feed_file.read_text().splitlines()
print(f"FEED_LINES: {len(lines)}")

