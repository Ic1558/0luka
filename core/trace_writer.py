import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import RUNTIME_LOGS_DIR
from core.snapshot_store import save_snapshot
from core.trace_versioning import CURRENT_VERSION

TRACE_FILE = RUNTIME_LOGS_DIR / "activity_feed.jsonl"
TRACE_VERSION = CURRENT_VERSION

REQUIRED_FIELDS = [
    "execution_mode",
    "normalized_task",
    "decision",
    "result",
]


def write_trace(payload: dict, trace_id: str = None):
    trace_id = trace_id or str(uuid.uuid4())

    record = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_version": TRACE_VERSION,
        "parent_trace_id": payload.get("parent_trace_id"),
        "execution_mode": payload.get("execution_mode"),
        "normalized_task": payload.get("normalized_task"),
        "decision": payload.get("decision"),
        "command": payload.get("command"),
        "result": payload.get("result"),
        "error": payload.get("error"),
    }

    for field in REQUIRED_FIELDS:
        if record.get(field) is None:
            raise ValueError(f"trace_writer: missing required field '{field}' — refusing partial write")

    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(TRACE_FILE, "a") as f:
        f.write(line)
        f.flush()

    # --- snapshot linkage ---
    state_before = payload.get("state_before")
    state_after = payload.get("state_after")
    if state_before is not None and state_after is not None:
        save_snapshot(trace_id, state_before, state_after)

    return trace_id
