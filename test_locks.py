import os
import json
from pathlib import Path
os.environ["LUKA_RUNTIME_ROOT"] = "/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.zMKpoucCIp"
from core.activity_feed_guard import guarded_append_activity_feed

payload = {"ts_utc": "2026-03-04T00:00:00Z", "action": "lock_test"}
# This will call _ensure_anchor_atomic (which locks) 
# and then it will lock again in its own block.
try:
    ok = guarded_append_activity_feed(Path("dummy"), payload)
    print(f"NESTED_LOCK_OK: {ok}")
except Exception as e:
    print(f"LOCK_ERROR: {e}")
