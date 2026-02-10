#!/usr/bin/env python3
"""Phase 4C regression tests for Task Submit API."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _setup_dirs(root: Path) -> None:
    (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "completed").mkdir(parents=True, exist_ok=True)


def _load_submit(root: Path):
    mod = importlib.import_module("core.submit")
    mod = importlib.reload(mod)
    mod.ROOT = root
    mod.INBOX = root / "interface" / "inbox"
    mod.OUTBOX = root / "interface" / "outbox" / "tasks"
    mod.COMPLETED = root / "interface" / "completed"
    return mod


def test_submit_flat_task() -> None:
    """Submit a flat task dict, verify receipt and inbox file."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            submit = _load_submit(root)
            receipt = submit.submit_task(
                {
                    "author": "codex",
                    "intent": "test.submit",
                    "schema_version": "clec.v1",
                    "ops": [{"op_id": "op1", "type": "write_text", "target_path": "test.txt", "content": "hello"}],
                    "verify": [],
                }
            )

            assert receipt["status"] == "submitted"
            assert receipt["task_id"]
            assert receipt["trace_id"]

            inbox_file = root / receipt["inbox_path"]
            assert inbox_file.exists(), "inbox file not created"

            content = inbox_file.read_text(encoding="utf-8")
            assert "/Users/" not in content, "hard path in inbox file"
            assert receipt["task_id"] in content
            print("test_submit_flat_task: ok")
        finally:
            _restore_env(old)


def test_submit_with_explicit_task_id() -> None:
    """Submit with explicit task_id, verify it's used."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            submit = _load_submit(root)
            receipt = submit.submit_task({"author": "test", "intent": "explicit.id"}, task_id="explicit_001")
            assert receipt["task_id"] == "explicit_001"
            assert (root / "interface" / "inbox" / "explicit_001.yaml").exists()
            print("test_submit_with_explicit_task_id: ok")
        finally:
            _restore_env(old)


def test_submit_rejects_duplicate() -> None:
    """Submit same task_id twice, second should fail."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            submit = _load_submit(root)
            submit.submit_task({"author": "test"}, task_id="dup_001")
            try:
                submit.submit_task({"author": "test"}, task_id="dup_001")
                raise AssertionError("should have rejected duplicate")
            except submit.SubmitError as exc:
                assert "duplicate" in str(exc)
            print("test_submit_rejects_duplicate: ok")
        finally:
            _restore_env(old)


def test_submit_rejects_hard_paths() -> None:
    """Task with /Users/ in payload should be rejected."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            submit = _load_submit(root)
            try:
                submit.submit_task({"author": "test", "intent": "hardpath", "target": "/Users/icmini/secret.txt"})
                raise AssertionError("should have rejected hard path")
            except submit.SubmitError as exc:
                assert "hard_path" in str(exc)
            print("test_submit_rejects_hard_paths: ok")
        finally:
            _restore_env(old)


def test_submit_native_envelope() -> None:
    """Submit a pre-formed envelope/v1, verify it's accepted."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            submit = _load_submit(root)
            envelope = {
                "v": "0luka.envelope/v1",
                "type": "task.request",
                "trace": {"trace_id": "env_001", "ts": "2026-02-08T00:00:00Z"},
                "source": {"actor": "openwork", "lane": "run"},
                "payload": {
                    "task": {
                        "task_id": "env_001",
                        "intent": "code.review",
                        "inputs": {},
                        "schema_version": "clec.v1",
                        "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
                        "verify": [],
                    }
                },
            }
            receipt = submit.submit_task(envelope)
            assert receipt["task_id"] == "env_001"
            assert receipt["trace_id"] == "env_001"
            assert (root / "interface" / "inbox" / "env_001.yaml").exists()
            print("test_submit_native_envelope: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_submit_flat_task()
    test_submit_with_explicit_task_id()
    test_submit_rejects_duplicate()
    test_submit_rejects_hard_paths()
    test_submit_native_envelope()
    print("test_submit: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
