import os
import json
from pathlib import Path
os.environ["LUKA_RUNTIME_ROOT"] = "/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/tmp.zMKpoucCIp"
from core.activity_feed_guard import guarded_append_activity_feed

payload = {"ts_utc": "2026-03-04T00:00:01Z", "action": "after_corruption"}
# Should detect that the last line is not the last hashed state
ok = guarded_append_activity_feed(Path("dummy"), payload)
print(f"APPEND_AFTER_CORRUPTION_OK: {ok}")
