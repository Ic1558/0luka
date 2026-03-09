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
    (root / "runtime_root" / "state" / "qs_runs").mkdir(parents=True, exist_ok=True)


def _reload_runtime_modules():
    for name in [
        "core.config",
        "interface.operator.mission_control_server",
        "tools.ops.runtime_validator",
        "core.activity_feed_guard",
        "tools.ops.runtime_guardian",
    ]:
        importlib.reload(importlib.import_module(name))


def _write_run_state(root: Path, run_id: str, payload: dict) -> None:
    path = root / "runtime_root" / "state" / "qs_runs" / f"{run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _write_outbox_projection(root: Path, run_id: str, payload: dict) -> None:
    ingress = dict(payload)
    ingress["status"] = payload.get("qs_status")
    path = root / "interface" / "outbox" / "tasks" / f"{run_id}.result.json"
    doc = {"status": "ok", "outputs": {"json": {"ingress": ingress}}}
    path.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _base_run(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "job_type": "qs.report_export",
        "project_id": "prj_guard",
        "qs_status": "completed",
        "artifacts": [],
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


def test_runtime_guardian_logs_clean_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_runtime_modules()
            clean = _base_run("guard_ok_001")
            _write_run_state(root, "guard_ok_001", clean)
            _write_outbox_projection(root, "guard_ok_001", clean)

            guardian = importlib.import_module("tools.ops.runtime_guardian")
            result = guardian.run_once(mode="full")

            assert result["ok"] is True
            entry = result["guardian_entry"]
            assert entry["severity"] == "healthy"
            assert entry["action"] == "none"
            assert entry["reason"] == "validator_clean"

            actions_log = root / "runtime_root" / "state" / "guardian_actions.jsonl"
            entries = [json.loads(line) for line in actions_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert entries[-1]["reason"] == "validator_clean"

            feed = root / "runtime_root" / "logs" / "activity_feed.jsonl"
            feed_rows = [json.loads(line) for line in feed.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert any(row.get("action") == "guardian_recovery" for row in feed_rows)
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_guardian_logs_projection_drift_as_report_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_runtime_modules()
            state_payload = _base_run("guard_bad_001")
            projection_payload = dict(state_payload)
            projection_payload["execution_status"] = "blocked"
            _write_run_state(root, "guard_bad_001", state_payload)
            _write_outbox_projection(root, "guard_bad_001", projection_payload)

            before_state = (root / "runtime_root" / "state" / "qs_runs" / "guard_bad_001.json").read_text(encoding="utf-8")

            guardian = importlib.import_module("tools.ops.runtime_guardian")
            result = guardian.run_once(mode="full")

            entry = result["guardian_entry"]
            assert entry["severity"] == "high"
            assert entry["action"] == "report_only"
            assert entry["reason"] == "projection_drift_detected"

            after_state = (root / "runtime_root" / "state" / "qs_runs" / "guard_bad_001.json").read_text(encoding="utf-8")
            assert before_state == after_state
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_runtime_guardian_logs_queue_error_as_freeze_and_alert() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_runtime_modules()
            (root / "interface" / "inbox" / "guard_dup.yaml").write_text("task_id: guard_dup\n", encoding="utf-8")
            (root / "interface" / "completed" / "guard_dup.yaml").write_text("task_id: guard_dup\n", encoding="utf-8")

            guardian = importlib.import_module("tools.ops.runtime_guardian")
            result = guardian.run_once(mode="quick")

            entry = result["guardian_entry"]
            assert entry["severity"] == "critical"
            assert entry["action"] == "freeze_and_alert"
            assert entry["reason"] == "queue_corruption_detected"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)
