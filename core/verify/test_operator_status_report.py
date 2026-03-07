from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.operator_status_report import build_operator_status_report, render_operator_status_report


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_json_output_structure_valid(monkeypatch, tmp_path: Path) -> None:
    telemetry_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(telemetry_root))
    _write_json(
        telemetry_root / "telemetry" / "ram_monitor.latest.json",
        {"pressure_level": "NORMAL", "decision": {"high_swap_activity": False, "latch_active": False}},
    )
    _write_json(telemetry_root / "telemetry" / "bridge_consumer.latest.json", {"status": "idle"})
    _write_json(
        telemetry_root / "telemetry" / "bridge_watchdog.latest.json",
        {"overall_status": "ok", "checks": {"inflight": {"status": "ok"}, "outbox": {"status": "ok"}}},
    )

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"system_health": {"status": "HEALTHY"}, "ledger_watchdog": {"ok": True}, "proof_pack": {"available": True, "ok": True}})
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.operator_status_report._port_running", lambda port: True)

    report = build_operator_status_report()

    assert list(report.keys()) == [
        "ok",
        "overall_status",
        "system_health",
        "ledger_status",
        "bridge_status",
        "memory_status",
        "api_server",
        "redis",
        "timestamp",
        "details",
        "errors",
    ]
    assert report["ok"] is True
    assert report["overall_status"] == "HEALTHY"


def test_human_report_renders(monkeypatch, tmp_path: Path) -> None:
    telemetry_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(telemetry_root))
    _write_json(
        telemetry_root / "telemetry" / "ram_monitor.latest.json",
        {"pressure_level": "NORMAL", "decision": {"high_swap_activity": False, "latch_active": False}},
    )
    _write_json(telemetry_root / "telemetry" / "bridge_consumer.latest.json", {"status": "idle"})
    _write_json(
        telemetry_root / "telemetry" / "bridge_watchdog.latest.json",
        {"overall_status": "ok", "checks": {"inflight": {"status": "ok"}, "outbox": {"status": "ok"}}},
    )

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"system_health": {"status": "HEALTHY"}, "ledger_watchdog": {"ok": True}, "proof_pack": {"available": True, "ok": True}})
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.operator_status_report._port_running", lambda port: True)

    rendered = render_operator_status_report(build_operator_status_report())

    assert "Operator Runtime Status" in rendered
    assert "System Health: HEALTHY" in rendered
    assert "Ledger Proof: VERIFIED" in rendered
    assert "Bridge" in rendered
    assert "Memory" in rendered


def test_missing_telemetry_file_handled_safely(monkeypatch, tmp_path: Path) -> None:
    telemetry_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(telemetry_root))

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"system_health": {"status": "HEALTHY"}, "ledger_watchdog": {"ok": True}, "proof_pack": {"available": True, "ok": True}})
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.operator_status_report._port_running", lambda port: True)

    report = build_operator_status_report()

    assert report["ok"] is True
    assert report["overall_status"] == "DEGRADED"
    assert any(item["error"] == "telemetry_missing" for item in report["errors"])


def test_degraded_memory_condition_detected(monkeypatch, tmp_path: Path) -> None:
    telemetry_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(telemetry_root))
    _write_json(
        telemetry_root / "telemetry" / "ram_monitor.latest.json",
        {"pressure_level": "CRITICAL", "decision": {"high_swap_activity": True, "latch_active": True, "composite_critical": True}},
    )
    _write_json(telemetry_root / "telemetry" / "bridge_consumer.latest.json", {"status": "idle"})
    _write_json(
        telemetry_root / "telemetry" / "bridge_watchdog.latest.json",
        {"overall_status": "ok", "checks": {"inflight": {"status": "ok"}, "outbox": {"status": "ok"}}},
    )

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"system_health": {"status": "HEALTHY"}, "ledger_watchdog": {"ok": True}, "proof_pack": {"available": True, "ok": True}})
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.operator_status_report._port_running", lambda port: True)

    report = build_operator_status_report()

    assert report["memory_status"] == "CRITICAL"
    assert report["overall_status"] == "DEGRADED"


def test_missing_ports_force_critical(monkeypatch, tmp_path: Path) -> None:
    telemetry_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(telemetry_root))
    _write_json(
        telemetry_root / "telemetry" / "ram_monitor.latest.json",
        {"pressure_level": "NORMAL", "decision": {"high_swap_activity": False, "latch_active": False}},
    )
    _write_json(telemetry_root / "telemetry" / "bridge_consumer.latest.json", {"status": "idle"})
    _write_json(
        telemetry_root / "telemetry" / "bridge_watchdog.latest.json",
        {"overall_status": "ok", "checks": {"inflight": {"status": "ok"}, "outbox": {"status": "ok"}}},
    )

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"system_health": {"status": "HEALTHY"}, "ledger_watchdog": {"ok": True}, "proof_pack": {"available": True, "ok": True}})
        if cmd == ["core/health.py", "--full", "--json"]:
            return _cp(args, 0, {"status": "healthy", "tests": {"passed": 21, "suites": 21}})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.operator_status_report._port_running", lambda port: False)

    report = build_operator_status_report()

    assert report["api_server"] == "MISSING"
    assert report["redis"] == "MISSING"
    assert report["overall_status"] == "CRITICAL"
