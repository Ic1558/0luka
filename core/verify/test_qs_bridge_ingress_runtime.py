#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import tempfile
from pathlib import Path

import yaml

ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
        "OUTBOX_ROOT": os.environ.get("OUTBOX_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    os.environ["OUTBOX_ROOT"] = str(root / "interface" / "outbox")
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _setup_dirs(root: Path) -> None:
    from core.verify._test_root import ensure_test_root

    ensure_test_root(root)
    (root / "runtime_root" / "logs").mkdir(parents=True, exist_ok=True)
    (root / "runtime_root" / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "runtime_root" / "state").mkdir(parents=True, exist_ok=True)


def _reload_modules():
    for name in [
        "core.config",
        "core.submit",
        "core.router",
        "core.task_dispatcher",
        "core.outbox_writer",
    ]:
        importlib.reload(importlib.import_module(name))


def _write_inbox_task(root: Path, task_id: str, status: str, *, malformed: bool = False) -> Path:
    payload = {
        "task_id": task_id,
        "author": "bridge",
        "call_sign": "[Bridge]",
        "root": "${ROOT}",
        "ts_utc": "2026-03-09T00:00:00Z",
        "created_at_utc": "2026-03-09T00:00:00Z",
        "intent": "qs.bridge_result.ingress",
        "schema_version": "clec.v1",
        "ops": [{"op_id": "ingress_noop", "type": "run", "command": "git status"}],
        "verify": [],
        "inputs": {
            "kind": "qs.runtime_result",
            "bridge_kind": "0luka.bridge_result",
            "run_id": task_id,
            "job_type": "qs.boq_generate",
            "project_id": "prj_rt",
            "status": status,
            "payload": {"kind": "qs.runtime_result", "run_id": task_id, "status": status, "body": {}},
        },
    }
    if malformed:
        payload["inputs"].pop("project_id", None)
    inbox_path = root / "interface" / "inbox" / f"{task_id}.yaml"
    inbox_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return inbox_path


def test_qs_bridge_ingress_accepts_completed_and_failed_and_rejects_malformed() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            completed = _write_inbox_task(root, "run_completed_001", "completed")
            failed = _write_inbox_task(root, "run_failed_001", "failed")
            malformed = _write_inbox_task(root, "run_bad_001", "completed", malformed=True)

            result_completed = dispatcher.dispatch_one(completed)
            result_failed = dispatcher.dispatch_one(failed)
            result_malformed = dispatcher.dispatch_one(malformed)

            assert result_completed["status"] == "committed"
            assert result_failed["status"] == "committed"
            assert result_malformed["status"] == "rejected"
            assert result_malformed["reason"] == "qs_bridge_ingress_missing:project_id"

            outbox_completed = json.loads((root / "interface" / "outbox" / "tasks" / "run_completed_001.result.json").read_text(encoding="utf-8"))
            outbox_failed = json.loads((root / "interface" / "outbox" / "tasks" / "run_failed_001.result.json").read_text(encoding="utf-8"))

            assert outbox_completed["status"] == "ok"
            assert outbox_failed["status"] == "ok"

            assert outbox_completed["outputs"]["json"]["ingress"]["run_id"] == "run_completed_001"
            assert outbox_completed["outputs"]["json"]["ingress"]["status"] == "completed"
            assert outbox_failed["outputs"]["json"]["ingress"]["run_id"] == "run_failed_001"
            assert outbox_failed["outputs"]["json"]["ingress"]["status"] == "failed"
            assert not (root / "interface" / "outbox" / "tasks" / "run_bad_001.result.json").exists()
            assert (root / "interface" / "rejected" / "run_bad_001.yaml").exists()
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_qs_bridge_ingress_duplicate_is_safely_skipped() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            inbox = _write_inbox_task(root, "run_dup_001", "completed")
            first = dispatcher.dispatch_one(inbox)
            duplicate = _write_inbox_task(root, "run_dup_001", "completed")
            second = dispatcher.dispatch_one(duplicate)

            assert first["status"] == "committed"
            assert second["status"] == "skipped"
            outbox = json.loads((root / "interface" / "outbox" / "tasks" / "run_dup_001.result.json").read_text(encoding="utf-8"))
            assert outbox["outputs"]["json"]["ingress"]["run_id"] == "run_dup_001"
            assert outbox["outputs"]["json"]["ingress"]["status"] == "completed"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_qs_bridge_ingress_accepts_completed_and_failed_and_rejects_malformed()
    test_qs_bridge_ingress_duplicate_is_safely_skipped()
    print("test_qs_bridge_ingress_runtime: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
