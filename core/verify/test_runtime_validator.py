#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import tempfile
from pathlib import Path

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
    (root / "runtime_root" / "state" / "qs_runs").mkdir(parents=True, exist_ok=True)


def _reload_modules():
    names = [
        "core.config",
        "interface.operator.mission_control_server",
        "tools.ops.runtime_validator",
    ]
    return {name: importlib.reload(importlib.import_module(name)) for name in names}


def _write_run_state(root: Path, run_id: str, payload: dict) -> None:
    path = root / "runtime_root" / "state" / "qs_runs" / f"{run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _write_outbox_projection(root: Path, run_id: str, payload: dict) -> None:
    ingress = dict(payload)
    ingress["status"] = payload.get("qs_status")
    path = root / "interface" / "outbox" / "tasks" / f"{run_id}.result.json"
    doc = {
        "status": "ok",
        "outputs": {
            "json": {
                "ingress": ingress,
            }
        },
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _base_run(run_id: str, *, artifacts: list[dict] | None = None) -> dict:
    return {
        "run_id": run_id,
        "job_type": "qs.report_export",
        "project_id": "prj_val",
        "qs_status": "completed",
        "artifacts": artifacts or [],
        "requires_approval": False,
        "approval_state": "not_required",
        "runtime_state": "accepted",
        "execution_status": "allowed",
        "block_reason": None,
        "approved_by": None,
        "approved_at": None,
        "approval_reason": None,
        "job_execution_state": "completed",
        "job_execution_error": None,
        "updated_at": "2026-03-09T00:00:00Z",
    }


def test_runtime_validator_full_passes_for_consistent_projection() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]

            payload = _base_run("run_ok_001")
            _write_run_state(root, "run_ok_001", payload)
            _write_outbox_projection(root, "run_ok_001", payload)

            report = validator.validate_runtime(mode="full")
            assert report["runtime_status"] == "healthy"
            assert report["runs_scanned"] == 1
            assert report["errors"] == []
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_validator_detects_approval_violation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]

            payload = _base_run("run_bad_approval")
            payload.update(
                {
                    "job_type": "qs.po_generate",
                    "requires_approval": True,
                    "approval_state": "pending_approval",
                    "runtime_state": "pending_approval",
                    "execution_status": "allowed",
                    "job_execution_state": "completed",
                }
            )
            _write_run_state(root, "run_bad_approval", payload)
            _write_outbox_projection(root, "run_bad_approval", payload)

            report = validator.validate_runtime(mode="full", run_id="run_bad_approval")
            assert report["runtime_status"] == "invalid"
            categories = [row["category"] for row in report["errors"]]
            assert "APPROVAL_ERROR" in categories
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_validator_detects_projection_drift() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]

            state_payload = _base_run("run_drift_001")
            projection_payload = dict(state_payload)
            projection_payload["execution_status"] = "blocked"
            _write_run_state(root, "run_drift_001", state_payload)
            _write_outbox_projection(root, "run_drift_001", projection_payload)

            report = validator.validate_runtime(mode="full", run_id="run_drift_001")
            assert report["runtime_status"] == "invalid"
            assert any(row["category"] == "PROJECTION_DRIFT" for row in report["errors"])
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_validator_detects_queue_duplication_in_quick_mode() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]

            inbox = root / "interface" / "inbox" / "dup_run.yaml"
            completed = root / "interface" / "completed" / "dup_run.yaml"
            inbox.write_text("task_id: dup_run\n", encoding="utf-8")
            completed.write_text("task_id: dup_run\n", encoding="utf-8")

            report = validator.validate_runtime(mode="quick")
            assert report["runtime_status"] == "invalid"
            assert any(row["category"] == "QUEUE_ERROR" for row in report["errors"])
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_validator_artifact_mode_detects_missing_files() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]

            payload = _base_run(
                "run_artifact_001",
                artifacts=[
                    {
                        "artifact_type": "report",
                        "path": "runtime_root/artifacts/qs/run_artifact_001/report.json",
                        "created_at": "2026-03-09T00:00:00Z",
                    }
                ],
            )
            _write_run_state(root, "run_artifact_001", payload)
            _write_outbox_projection(root, "run_artifact_001", payload)

            report = validator.validate_runtime(mode="full", run_id="run_artifact_001", strict_artifacts=True)
            assert report["runtime_status"] == "invalid"
            assert any(row["detail"].startswith("artifact_missing") for row in report["errors"])
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)
