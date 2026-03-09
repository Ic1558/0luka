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
    (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)


def _reload_modules():
    names = [
        "core.config",
        "tools.ops.runtime_validator",
        "tools.ops.runtime_guardian",
        "core.task_dispatcher",
        "core.phase1d_result_gate",
    ]
    return {name: importlib.reload(importlib.import_module(name)) for name in names}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def test_verification_chain_passes_for_committed_trace_and_writes_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]
            gate_mod = mods["core.phase1d_result_gate"]

            trace_id = "trace_ok_001"

            # outbox result containing provenance.trace_id
            _write_json(
                root / "interface" / "outbox" / "tasks" / "run_001.result.json",
                {"status": "ok", "provenance": {"trace_id": trace_id}, "outputs": {"json": {"ingress": {"run_id": "run_001"}}}},
            )

            # provenance line in authoritative jsonl (for this test, include trace_id explicitly)
            _write_jsonl(
                root / "observability" / "artifacts" / "run_provenance.jsonl",
                {"trace_id": trace_id, "run_id": "run_001", "job_type": "qs.report_generate"},
            )

            # activity feed match (many feeds correlate via task_id)
            _write_jsonl(
                root / "runtime_root" / "logs" / "activity_feed.jsonl",
                {"ts_utc": "2026-03-09T00:00:00Z", "task_id": trace_id, "hash": "h1", "prev_hash": "p1"},
            )

            # Make the outbound gate deterministic for this unit test (avoid schema dependency).
            gate_mod.gate_outbound_result = lambda rb, mode="normal": rb  # type: ignore[assignment]

            out = validator.run_verification_chain(trace_id)
            assert out["verdict"] == "verified"
            assert out["gates"]["provenance_exists"] is True
            assert out["gates"]["activity_feed_present"] is True
            assert out["gates"]["outbound_result_gate"] == "passed"

            artifact_path = root / "runtime_root" / "artifacts" / "tasks" / trace_id / "verification.json"
            assert artifact_path.exists()
            disk = json.loads(artifact_path.read_text(encoding="utf-8"))
            assert disk["trace_id"] == trace_id
            assert disk["verdict"] == "verified"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_verification_chain_fails_on_missing_provenance() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            validator = mods["tools.ops.runtime_validator"]
            gate_mod = mods["core.phase1d_result_gate"]

            trace_id = "trace_missing_prov"
            _write_json(
                root / "interface" / "outbox" / "tasks" / "run_002.result.json",
                {"status": "ok", "provenance": {"trace_id": trace_id}, "outputs": {"json": {"ingress": {"run_id": "run_002"}}}},
            )
            _write_jsonl(
                root / "runtime_root" / "logs" / "activity_feed.jsonl",
                {"ts_utc": "2026-03-09T00:00:00Z", "task_id": trace_id},
            )

            gate_mod.gate_outbound_result = lambda rb, mode="normal": rb  # type: ignore[assignment]
            out = validator.run_verification_chain(trace_id)
            assert out["verdict"] == "failed"
            assert out["gates"]["provenance_exists"] is False
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_enforce_evidence_minimum_freezes_when_failed() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            guardian = mods["tools.ops.runtime_guardian"]

            out = guardian.enforce_evidence_minimum("trace_unknown")
            assert out["guardian_action"] == "freeze_and_alert"
            assert out["reason"] == "min_evidence_failed"
            assert out["verification"]["verdict"] == "failed"
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def test_epoch_manifest_written_on_startup_helper_invocation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            mods = _reload_modules()
            dispatcher = mods["core.task_dispatcher"]

            # Monkeypatch subprocess.run used by _emit_startup_epoch_marker to simulate a successful emit.
            def _fake_run(cmd, capture_output=True, text=True, check=False, timeout=2.0):  # noqa: ANN001
                manifest = root / "runtime_root" / "logs" / "epoch_manifest.jsonl"
                _write_jsonl(manifest, {"event": "epoch_marker", "epoch_id": 1, "epoch_hash": "x" * 64, "prev_epoch_hash": "0" * 64, "log_heads": {}, "ts_utc": "2026-03-09T00:00:00Z"})

                class _Proc:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                return _Proc()

            dispatcher.subprocess.run = _fake_run  # type: ignore[assignment]
            dispatcher._emit_startup_epoch_marker()
            assert (root / "runtime_root" / "logs" / "epoch_manifest.jsonl").exists()
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)

