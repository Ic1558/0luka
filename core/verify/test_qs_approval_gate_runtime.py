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
        "core.qs_runtime_state",
        "core.router",
        "core.task_dispatcher",
        "core.outbox_writer",
    ]:
        importlib.reload(importlib.import_module(name))


def _write_inbox_task(root: Path, task_id: str, job_type: str) -> Path:
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
            "job_type": job_type,
            "project_id": "prj_qs",
            "status": "completed",
            "payload": {"kind": "qs.runtime_result", "run_id": task_id, "status": "completed", "body": {}},
        },
    }
    inbox_path = root / "interface" / "inbox" / f"{task_id}.yaml"
    inbox_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return inbox_path


def _load_run_state(root: Path, run_id: str) -> dict:
    return json.loads((root / "runtime_root" / "state" / "qs_runs" / f"{run_id}.json").read_text(encoding="utf-8"))


def test_po_generate_enters_pending_approval_and_can_be_approved() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")
            qs_state = importlib.import_module("core.qs_runtime_state")

            inbox = _write_inbox_task(root, "run_po_001", "qs.po_generate")
            result = dispatcher.dispatch_one(inbox)
            assert result["status"] == "committed"

            outbox = json.loads((root / "interface" / "outbox" / "tasks" / "run_po_001.result.json").read_text(encoding="utf-8"))
            ingress = outbox["outputs"]["json"]["ingress"]
            assert ingress["run_id"] == "run_po_001"
            assert ingress["job_type"] == "qs.po_generate"
            assert ingress["status"] == "completed"
            assert ingress["runtime_state"] == "pending_approval"
            assert ingress["approval_state"] == "pending_approval"
            assert ingress["execution_status"] == "blocked"
            assert ingress["block_reason"] == "approval_required"
            assert ingress["requires_approval"] is True

            state_before = _load_run_state(root, "run_po_001")
            assert state_before["runtime_state"] == "pending_approval"
            assert state_before["execution_status"] == "blocked"

            approved = qs_state.approve_run("run_po_001", actor="Boss", reason="approved for issue")
            assert approved["runtime_state"] == "approved"
            assert approved["approval_state"] == "approved"
            assert approved["execution_status"] == "allowed"
            assert approved["approved_by"] == "Boss"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_po_generate_can_be_rejected_by_operator() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")
            qs_state = importlib.import_module("core.qs_runtime_state")

            inbox = _write_inbox_task(root, "run_po_002", "qs.po_generate")
            result = dispatcher.dispatch_one(inbox)
            assert result["status"] == "committed"

            rejected = qs_state.reject_run("run_po_002", actor="Boss", reason="operator denied")
            assert rejected["runtime_state"] == "rejected_by_operator"
            assert rejected["approval_state"] == "rejected_by_operator"
            assert rejected["execution_status"] == "blocked"
            assert rejected["block_reason"] == "operator_rejected"
            assert rejected["approved_by"] == "Boss"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_non_approval_job_executes_without_gate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            inbox = _write_inbox_task(root, "run_report_001", "qs.report_export")
            result = dispatcher.dispatch_one(inbox)
            assert result["status"] == "committed"

            outbox = json.loads((root / "interface" / "outbox" / "tasks" / "run_report_001.result.json").read_text(encoding="utf-8"))
            ingress = outbox["outputs"]["json"]["ingress"]
            assert ingress["job_type"] == "qs.report_export"
            assert ingress["runtime_state"] == "accepted"
            assert ingress["approval_state"] == "not_required"
            assert ingress["execution_status"] == "allowed"
            assert ingress["block_reason"] is None
            assert ingress["requires_approval"] is False

            state = _load_run_state(root, "run_report_001")
            assert state["runtime_state"] == "accepted"
            assert state["execution_status"] == "allowed"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_po_generate_enters_pending_approval_and_can_be_approved()
    test_po_generate_can_be_rejected_by_operator()
    test_non_approval_job_executes_without_gate()
    print("test_qs_approval_gate_runtime: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
