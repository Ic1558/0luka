from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.runtime_status_report import build_runtime_status_report, render_runtime_status_report


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def _patch_env(monkeypatch, tmp_path: Path) -> Path:
    runtime_root = tmp_path / "runtime"
    exports = runtime_root / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    return runtime_root


def test_healthy_path_with_all_sources_available(monkeypatch, tmp_path: Path) -> None:
    runtime_root = _patch_env(monkeypatch, tmp_path)
    export_dir = runtime_root / "exports" / "ledger_proof_20260307T000000Z"
    export_dir.mkdir()

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": True},
                    },
                },
            )
        if cmd == ["tools/ops/proof_report.py", "--path", str(export_dir), "--json"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "epoch_id": 64,
                    "leaf_count": 23,
                    "segment_seq_min": 1,
                    "segment_seq_max": 23,
                    "merkle_root": "abc123",
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = build_runtime_status_report()

    assert report["ok"] is True
    assert report["overall_status"] == "HEALTHY"
    assert report["system_health"] == {"status": "HEALTHY", "passed": 21, "total": 21}
    assert report["ledger_watchdog"]["ok"] is True
    assert report["proof_pack"]["available"] is True
    assert report["proof_pack"]["ok"] is True


def test_proof_pack_unavailable_is_degraded(monkeypatch, tmp_path: Path) -> None:
    _patch_env(monkeypatch, tmp_path)

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": True},
                    },
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = build_runtime_status_report()

    assert report["ok"] is False
    assert report["overall_status"] == "DEGRADED"
    assert report["proof_pack"]["available"] is False
    assert {"error": "proof_pack_unavailable"} in report["errors"]


def test_watchdog_fail_is_failed(monkeypatch, tmp_path: Path) -> None:
    runtime_root = _patch_env(monkeypatch, tmp_path)
    export_dir = runtime_root / "exports" / "ledger_proof_20260307T000000Z"
    export_dir.mkdir()

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                2,
                {
                    "ok": False,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": False},
                    },
                },
            )
        if cmd == ["tools/ops/proof_report.py", "--path", str(export_dir), "--json"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "epoch_id": 64,
                    "leaf_count": 23,
                    "segment_seq_min": 1,
                    "segment_seq_max": 23,
                    "merkle_root": "abc123",
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = build_runtime_status_report()

    assert report["overall_status"] == "FAILED"
    assert {"error": "ledger_watchdog_failed"} in report["errors"]


def test_health_fail_is_failed(monkeypatch, tmp_path: Path) -> None:
    runtime_root = _patch_env(monkeypatch, tmp_path)
    export_dir = runtime_root / "exports" / "ledger_proof_20260307T000000Z"
    export_dir.mkdir()

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 1, {"status": "degraded", "tests": {"passed": 20, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": True},
                    },
                },
            )
        if cmd == ["tools/ops/proof_report.py", "--path", str(export_dir), "--json"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "epoch_id": 64,
                    "leaf_count": 23,
                    "segment_seq_min": 1,
                    "segment_seq_max": 23,
                    "merkle_root": "abc123",
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = build_runtime_status_report()

    assert report["overall_status"] == "FAILED"
    assert {"error": "system_health_failed"} in report["errors"]


def test_human_output_contains_required_sections(monkeypatch, tmp_path: Path) -> None:
    runtime_root = _patch_env(monkeypatch, tmp_path)
    export_dir = runtime_root / "exports" / "ledger_proof_20260307T000000Z"
    export_dir.mkdir()

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": True},
                    },
                },
            )
        if cmd == ["tools/ops/proof_report.py", "--path", str(export_dir), "--json"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "epoch_id": 64,
                    "leaf_count": 23,
                    "segment_seq_min": 1,
                    "segment_seq_max": 23,
                    "merkle_root": "abc123",
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    rendered = render_runtime_status_report(build_runtime_status_report())

    assert "0luka Runtime Status Report" in rendered
    assert "System Health" in rendered
    assert "Ledger Watchdog" in rendered
    assert "Proof Pack" in rendered
    assert "Overall" in rendered
    assert "result: HEALTHY" in rendered


def test_json_contract_shape_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    runtime_root = _patch_env(monkeypatch, tmp_path)
    export_dir = runtime_root / "exports" / "ledger_proof_20260307T000000Z"
    export_dir.mkdir()

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        if cmd == ["tools/ops/ledger_watchdog.py", "--check-epoch", "--json", "--no-report", "--no-emit"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "checks": {
                        "active_feed": {"ok": True},
                        "epoch_manifest": {"ok": True},
                        "rotated_feeds": {"ok": True},
                        "segment_integrity": {"ok": True},
                        "segment_chain": {"ok": True},
                        "ledger_root": {"ok": True},
                    },
                },
            )
        if cmd == ["tools/ops/proof_report.py", "--path", str(export_dir), "--json"]:
            return _cp(
                args,
                0,
                {
                    "ok": True,
                    "epoch_id": 64,
                    "leaf_count": 23,
                    "segment_seq_min": 1,
                    "segment_seq_max": 23,
                    "merkle_root": "abc123",
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = build_runtime_status_report()

    assert list(report.keys()) == [
        "ok",
        "system_health",
        "ledger_watchdog",
        "proof_pack",
        "overall_status",
        "errors",
    ]
    assert list(report["system_health"].keys()) == ["status", "passed", "total"]
    assert list(report["proof_pack"].keys()) == [
        "available",
        "path",
        "ok",
        "epoch_id",
        "leaf_count",
        "segment_seq_min",
        "segment_seq_max",
        "merkle_root",
    ]
