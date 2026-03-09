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
        "PYTHONPATH": os.environ.get("PYTHONPATH"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    os.environ["OUTBOX_ROOT"] = str(root / "interface" / "outbox")
    os.environ["PYTHONPATH"] = f"{ROOT_REPO / 'repos' / 'qs' / 'src'}:{ROOT_REPO}"
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


def _reload_modules() -> None:
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
            "project_id": "prj_wiring",
            "status": "completed",
            "payload": {
                "kind": "qs.runtime_result",
                "run_id": task_id,
                "job_type": job_type,
                "project_id": "prj_wiring",
                "status": "completed",
                "body": {"envelope_payload": {"artifact_refs": []}},
            },
        },
    }
    path = root / "interface" / "inbox" / f"{task_id}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _load_state(root: Path, run_id: str) -> dict:
    return json.loads((root / "runtime_root" / "state" / "qs_runs" / f"{run_id}.json").read_text(encoding="utf-8"))


def _load_outbox(root: Path, run_id: str) -> dict:
    return json.loads((root / "interface" / "outbox" / "tasks" / f"{run_id}.result.json").read_text(encoding="utf-8"))


def test_non_approval_job_executes_immediately_and_persists_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            task = _write_inbox_task(root, "run_exec_001", "qs.report_export")
            result = dispatcher.dispatch_one(task)
            assert result["status"] == "committed"

            state = _load_state(root, "run_exec_001")
            assert state["execution_status"] == "allowed"
            assert state["job_execution_state"] == "completed"
            assert state["job_execution_error"] is None
            assert state["artifacts"] == [
                {
                    "artifact_type": "summary_report",
                    "path": "artifacts/report/run_exec_001/project_qs_report.md",
                }
            ]

            outbox = _load_outbox(root, "run_exec_001")
            ingress = outbox["outputs"]["json"]["ingress"]
            assert ingress["artifacts"] == state["artifacts"]
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_approval_gated_job_not_executed_before_approval() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            task = _write_inbox_task(root, "run_exec_002", "qs.po_generate")
            result = dispatcher.dispatch_one(task)
            assert result["status"] == "committed"

            state = _load_state(root, "run_exec_002")
            assert state["approval_state"] == "pending_approval"
            assert state["execution_status"] == "blocked"
            assert state["job_execution_state"] == "not_started"
            assert state["artifacts"] == []
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_approval_gated_job_executes_after_approval_and_projects_to_mission_control() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")
            qs_state = importlib.import_module("core.qs_runtime_state")
            mission = importlib.import_module("interface.operator.mission_control_server")

            task = _write_inbox_task(root, "run_exec_003", "qs.po_generate")
            result = dispatcher.dispatch_one(task)
            assert result["status"] == "committed"

            approved = qs_state.approve_run("run_exec_003", actor="Boss", reason="approve for release")
            assert approved["approval_state"] == "approved"
            assert approved["execution_status"] == "allowed"
            assert approved["job_execution_state"] == "completed"
            assert approved["artifacts"] == [
                {
                    "artifact_type": "po_document",
                    "path": "artifacts/po/run_exec_003/po_document.md",
                }
            ]

            run_view = mission.load_qs_run("run_exec_003")
            assert run_view["run"]["artifacts"] == approved["artifacts"]
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_unknown_job_type_fails_closed_without_fabricated_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")

            task = _write_inbox_task(root, "run_exec_004", "qs.unknown")
            result = dispatcher.dispatch_one(task)
            assert result["status"] == "rejected"
            state = _load_state(root, "run_exec_004")
            assert state["execution_status"] == "failed"
            assert state["job_execution_state"] == "failed"
            assert state["artifacts"] == []
            assert not (root / "interface" / "outbox" / "tasks" / "run_exec_004.result.json").exists()
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_non_approval_job_executes_immediately_and_persists_artifacts()
    test_approval_gated_job_not_executed_before_approval()
    test_approval_gated_job_executes_after_approval_and_projects_to_mission_control()
    test_unknown_job_type_fails_closed_without_fabricated_artifacts()
    print("test_qs_runtime_job_registry_wiring: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
