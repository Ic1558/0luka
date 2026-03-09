#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
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
        "interface.operator.mission_control_server",
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
            "project_id": "prj_proj",
            "status": "completed",
            "payload": {"kind": "qs.runtime_result", "run_id": task_id, "status": "completed", "body": {}},
        },
    }
    inbox_path = root / "interface" / "inbox" / f"{task_id}.yaml"
    inbox_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return inbox_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_qs_mission_control_projection_is_truthful_and_read_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")
            qs_state = importlib.import_module("core.qs_runtime_state")
            mission = importlib.import_module("interface.operator.mission_control_server")

            dispatcher.dispatch_one(_write_inbox_task(root, "run_po_pending", "qs.po_generate"))
            dispatcher.dispatch_one(_write_inbox_task(root, "run_po_approved", "qs.po_generate"))
            dispatcher.dispatch_one(_write_inbox_task(root, "run_report_ok", "qs.report_export"))
            qs_state.approve_run("run_po_approved", actor="Boss", reason="release approved")

            pending_path = root / "runtime_root" / "state" / "qs_runs" / "run_po_pending.json"
            approved_path = root / "runtime_root" / "state" / "qs_runs" / "run_po_approved.json"
            report_path = root / "runtime_root" / "state" / "qs_runs" / "run_report_ok.json"
            before_hashes = {path.name: _sha256(path) for path in [pending_path, approved_path, report_path]}

            pending = mission.load_qs_run("run_po_pending")
            approved = mission.load_qs_run("run_po_approved")
            report = mission.load_qs_run("run_report_ok")
            summary = mission.load_qs_runs_summary()

            assert pending["run"]["run_id"] == "run_po_pending"
            assert pending["run"]["job_type"] == "qs.po_generate"
            assert pending["run"]["project_id"] == "prj_proj"
            assert pending["run"]["qs_status"] == "completed"
            assert pending["run"]["approval_state"] == "pending_approval"
            assert pending["run"]["execution_status"] == "blocked"
            assert pending["run"]["block_reason"] == "approval_required"

            assert approved["run"]["run_id"] == "run_po_approved"
            assert approved["run"]["approval_state"] == "approved"
            assert approved["run"]["execution_status"] == "allowed"
            assert approved["run"]["approved_by"] == "Boss"
            assert approved["run"]["approval_reason"] == "release approved"

            assert report["run"]["run_id"] == "run_report_ok"
            assert report["run"]["job_type"] == "qs.report_export"
            assert report["run"]["approval_state"] == "not_required"
            assert report["run"]["execution_status"] == "allowed"

            assert summary["summary"]["blocked_runs"] == 1
            assert summary["summary"]["allowed_runs"] == 2
            assert summary["summary"]["pending_approval_runs"] == 1
            assert summary["summary"]["approved_runs"] == 1
            assert summary["summary"]["not_required_runs"] == 1

            after_hashes = {path.name: _sha256(path) for path in [pending_path, approved_path, report_path]}
            assert before_hashes == after_hashes
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_qs_mission_control_projection_is_truthful_and_read_only()
    print("test_qs_mission_control_projection: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
