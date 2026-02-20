#!/usr/bin/env python3
"""Tests for watchdog module."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
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


def _setup_dirs(root: Path) -> None:
    import shutil

    (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "incidents").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[2] / "interface" / "schemas"
    dst = root / "interface" / "schemas"
    dst.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)


def test_heartbeat_missing():
    """check_heartbeat reports missing when no file exists."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old = _set_env(root)
        try:
            import importlib
            import tools.ops.watchdog as wd
            wd = importlib.reload(wd)
            wd.ROOT = root
            wd.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
            wd.WATCHDOG_LOG = root / "observability" / "incidents" / "watchdog.jsonl"
            wd.INBOX_DIR = root / "interface" / "inbox"

            result = wd.check_heartbeat()
            assert result["stale"] is True
            assert result["status"] == "missing"
        finally:
            _restore_env(old)


def test_heartbeat_fresh():
    """check_heartbeat reports not stale when heartbeat is recent."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_dirs(root)
        old = _set_env(root)
        try:
            import importlib
            import tools.ops.watchdog as wd
            wd = importlib.reload(wd)
            wd.ROOT = root
            hb_path = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
            wd.HEARTBEAT_PATH = hb_path
            wd.WATCHDOG_LOG = root / "observability" / "incidents" / "watchdog.jsonl"
            wd.INBOX_DIR = root / "interface" / "inbox"

            hb = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "watching",
                "pid": os.getpid(),
            }
            hb_path.write_text(json.dumps(hb), encoding="utf-8")

            result = wd.check_heartbeat()
            assert result["stale"] is False
            assert result["status"] == "watching"
        finally:
            _restore_env(old)


def test_stuck_tasks_detected():
    """check_stuck_tasks finds tasks older than threshold."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_dirs(root)
        old = _set_env(root)
        try:
            import importlib
            import tools.ops.watchdog as wd
            wd = importlib.reload(wd)
            wd.ROOT = root
            wd.INBOX_DIR = root / "interface" / "inbox"
            wd.STUCK_TASK_SEC = 0  # any age is "stuck" for testing

            task_file = wd.INBOX_DIR / "task_test_stuck.yaml"
            task_file.write_text("intent: test\n", encoding="utf-8")

            stuck = wd.check_stuck_tasks()
            assert len(stuck) >= 1
            assert stuck[0]["file"] == "task_test_stuck.yaml"
        finally:
            _restore_env(old)


def test_tmp_cleanup():
    """clean_tmp_files removes old .tmp files."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _setup_dirs(root)
        old = _set_env(root)
        try:
            import importlib
            import tools.ops.watchdog as wd
            wd = importlib.reload(wd)
            wd.ROOT = root
            wd.WATCHDOG_LOG = root / "observability" / "incidents" / "watchdog.jsonl"

            # Create a .tmp file and backdate it
            tmp_file = root / "observability" / "artifacts" / "old.tmp"
            tmp_file.write_text("stale", encoding="utf-8")
            old_time = time.time() - 600  # 10 minutes ago
            os.utime(tmp_file, (old_time, old_time))

            cleaned = wd.clean_tmp_files()
            assert cleaned >= 1
            assert not tmp_file.exists()
        finally:
            _restore_env(old)


if __name__ == "__main__":
    test_heartbeat_missing()
    test_heartbeat_fresh()
    test_stuck_tasks_detected()
    test_tmp_cleanup()
    print("test_watchdog: 4/4 passed")
