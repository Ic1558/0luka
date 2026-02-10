#!/usr/bin/env python3
"""Phase 5C regression tests for Dispatch Ledger."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_ledger(root: Path):
    mod = importlib.import_module("core.ledger")
    mod = importlib.reload(mod)
    mod.ROOT = root
    mod.LEDGER_PATH = root / "observability" / "artifacts" / "dispatch_ledger.json"
    mod.DISPATCH_LOG = root / "observability" / "logs" / "dispatcher.jsonl"
    return mod


def test_ledger_append_and_query() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        ledger = _load_ledger(root)
        ledger.append_entry("task_001", "committed", author="codex", intent="test")
        ledger.append_entry("task_002", "rejected", author="gmx", intent="audit")
        ledger.append_entry("task_003", "committed", author="codex", intent="build")

        all_entries = ledger.query()
        assert len(all_entries) == 3

        committed = ledger.query(status="committed")
        assert len(committed) == 2
        rejected = ledger.query(status="rejected")
        assert len(rejected) == 1
        assert rejected[0]["task_id"] == "task_002"

        print("test_ledger_append_and_query: ok")
        _restore_env(old)


def test_ledger_deduplicates() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        ledger = _load_ledger(root)
        ledger.append_entry("dup_001", "committed")
        ledger.append_entry("dup_001", "committed")
        ledger.append_entry("dup_001", "rejected")

        entries = ledger.query()
        assert len(entries) == 1
        assert entries[0]["status"] == "committed"

        print("test_ledger_deduplicates: ok")
        _restore_env(old)


def test_ledger_rebuild_from_log() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)
        (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)

        log = root / "observability" / "logs" / "dispatcher.jsonl"
        lines = [
            json.dumps({"task_id": "log_001", "status": "committed", "ts": "2026-02-08T10:00:00Z"}),
            json.dumps({"task_id": "log_002", "status": "rejected", "ts": "2026-02-08T11:00:00Z"}),
            json.dumps({"event": "watch_start", "ts": "2026-02-08T09:00:00Z"}),
            json.dumps({"task_id": "log_003", "status": "error", "ts": "2026-02-08T12:00:00Z"}),
        ]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ledger = _load_ledger(root)
        result = ledger.rebuild_from_log()
        assert len(result["entries"]) == 3
        assert result["summary"]["committed"] == 1
        assert result["summary"]["rejected"] == 1
        assert result["summary"]["error"] == 1

        print("test_ledger_rebuild_from_log: ok")
        _restore_env(old)


def test_ledger_summary_correct() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        ledger = _load_ledger(root)
        ledger.append_entry("s1", "committed", ts="2026-02-08T01:00:00Z")
        ledger.append_entry("s2", "committed", ts="2026-02-08T02:00:00Z")
        ledger.append_entry("s3", "rejected", ts="2026-02-08T03:00:00Z")

        data = ledger._load_ledger()
        summary = data["summary"]
        assert summary["total"] == 3
        assert summary["committed"] == 2
        assert summary["rejected"] == 1
        assert summary["first_dispatch"] == "2026-02-08T01:00:00Z"
        assert summary["last_dispatch"] == "2026-02-08T03:00:00Z"

        print("test_ledger_summary_correct: ok")
        _restore_env(old)


def main() -> int:
    test_ledger_append_and_query()
    test_ledger_deduplicates()
    test_ledger_rebuild_from_log()
    test_ledger_summary_correct()
    print("test_ledger: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
