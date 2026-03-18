import json
import os
from datetime import datetime, timezone
from pathlib import Path

_SNAPSHOTS_DIR = Path.home() / "0luka/observability/snapshots"


def _snapshots_dir() -> Path:
    d = _SNAPSHOTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_path(trace_id: str) -> Path:
    return _snapshots_dir() / f"snapshot_{trace_id}.json"


def save_snapshot(trace_id: str, state_before: dict, state_after: dict) -> None:
    record = {
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state_before": state_before,
        "state_after": state_after,
    }
    path = _snapshot_path(trace_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False))
    os.replace(tmp, path)


def load_snapshot(trace_id: str):
    path = _snapshot_path(trace_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
