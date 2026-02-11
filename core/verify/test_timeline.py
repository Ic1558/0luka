#!/usr/bin/env python3
"""Tests for timeline module."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT")}
    os.environ["ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def test_emit_creates_timeline():
    """emit_event creates timeline.jsonl under trace_id directory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = _set_env(root)
        try:
            import importlib
            import core.timeline as tl
            tl = importlib.reload(tl)
            tl.ROOT = root
            tl.ARTIFACTS_DIR = root / "observability" / "artifacts" / "tasks"

            path = tl.emit_event("trace-001", "task-001", "START", phase="submit", agent_id="test")
            assert path.exists()
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1
            event = json.loads(lines[0])
            assert event["event"] == "START"
            assert event["task_id"] == "task-001"
            assert event["trace_id"] == "trace-001"
            assert event["phase"] == "submit"
        finally:
            _restore_env(old)


def test_emit_appends_events():
    """Multiple emit_event calls append to the same timeline."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = _set_env(root)
        try:
            import importlib
            import core.timeline as tl
            tl = importlib.reload(tl)
            tl.ROOT = root
            tl.ARTIFACTS_DIR = root / "observability" / "artifacts" / "tasks"

            tl.emit_event("trace-002", "task-002", "START", phase="submit")
            tl.emit_event("trace-002", "task-002", "DISPATCHED", phase="gate")
            tl.emit_event("trace-002", "task-002", "RUNNING", phase="execute")

            events = tl.read_timeline("trace-002")
            assert len(events) == 3
            assert [e["event"] for e in events] == ["START", "DISPATCHED", "RUNNING"]
        finally:
            _restore_env(old)


def test_read_empty_timeline():
    """read_timeline returns empty list for nonexistent trace."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = _set_env(root)
        try:
            import importlib
            import core.timeline as tl
            tl = importlib.reload(tl)
            tl.ROOT = root
            tl.ARTIFACTS_DIR = root / "observability" / "artifacts" / "tasks"

            events = tl.read_timeline("nonexistent-trace")
            assert events == []
        finally:
            _restore_env(old)


def test_emit_with_detail():
    """emit_event includes detail field when provided."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = _set_env(root)
        try:
            import importlib
            import core.timeline as tl
            tl = importlib.reload(tl)
            tl.ROOT = root
            tl.ARTIFACTS_DIR = root / "observability" / "artifacts" / "tasks"

            tl.emit_event("trace-003", "task-003", "DROPPED", phase="gate", detail="gate_rejected:no_ops")

            events = tl.read_timeline("trace-003")
            assert len(events) == 1
            assert events[0]["event"] == "DROPPED"
            assert events[0]["detail"] == "gate_rejected:no_ops"
        finally:
            _restore_env(old)


if __name__ == "__main__":
    test_emit_creates_timeline()
    test_emit_appends_events()
    test_read_empty_timeline()
    test_emit_with_detail()
    print("test_timeline: 4/4 passed")
