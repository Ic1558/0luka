"""AG-P5: Tool Dispatcher — validate, execute, and record evidence for tool calls."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dispatch_tool(
    tool_name: str,
    payload: dict,
    *,
    operator_id: str = "system",
    inference_id: str | None = None,
) -> dict:
    """Dispatch a named tool call, write evidence record, return result.

    Fail-closed: unknown tool → status=error, never raises.
    """
    from runtime.tools.registry import get_tool

    dispatch_id = str(uuid.uuid4())
    ts = _now()
    sd = _state_dir()

    tool_entry = get_tool(tool_name)
    if tool_entry is None:
        record = {
            "dispatch_id": dispatch_id,
            "tool_name": tool_name,
            "operator_id": operator_id,
            "inference_id": inference_id,
            "status": "error",
            "error": f"tool_not_registered:{tool_name}",
            "result": None,
            "ts_dispatched": ts,
            "governed": True,
        }
        _append_jsonl(sd / "tool_dispatch_log.jsonl", record)
        return record

    try:
        result = tool_entry["fn"](payload)
        status = "executed" if result.get("ok") else "tool_error"
        record = {
            "dispatch_id": dispatch_id,
            "tool_name": tool_name,
            "operator_id": operator_id,
            "inference_id": inference_id,
            "status": status,
            "error": result.get("error"),
            "result": result,
            "ts_dispatched": ts,
            "governed": True,
        }
    except Exception as exc:
        record = {
            "dispatch_id": dispatch_id,
            "tool_name": tool_name,
            "operator_id": operator_id,
            "inference_id": inference_id,
            "status": "error",
            "error": str(exc)[:300],
            "result": None,
            "ts_dispatched": ts,
            "governed": True,
        }

    _atomic_write(sd / "tool_dispatch_latest.json", record)
    _append_jsonl(sd / "tool_dispatch_log.jsonl", record)

    # Update index
    idx_path = sd / "tool_dispatch_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({
        "dispatch_id": dispatch_id,
        "tool_name": tool_name,
        "status": record["status"],
        "ts_dispatched": ts,
    })
    _atomic_write(idx_path, idx)

    return record


def get_dispatch_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "tool_dispatch_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_dispatches() -> list:
    sd = _state_dir()
    p = sd / "tool_dispatch_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
