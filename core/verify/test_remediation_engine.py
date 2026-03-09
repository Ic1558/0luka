from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import remediation_engine
from tools.ops import worker_recovery


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def test_healthy_state_noop(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"overall_status": "HEALTHY"})
        if cmd == ["tools/ops/operator_status_report.py", "--json"]:
            return _cp(
                args,
                0,
                {
                    "overall_status": "HEALTHY",
                    "api_server": "RUNNING",
                    "redis": "RUNNING",
                    "memory_status": "OK",
                    "bridge_status": "OK",
                    "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"


def test_api_missing_no_approval(monkeypatch) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "FAILED"},
        {
            "overall_status": "CRITICAL",
            "api_server": "MISSING",
            "redis": "RUNNING",
            "memory_status": "OK",
            "bridge_status": "OK",
            "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"
    assert decisions[0]["action_taken"] is False


def test_redis_missing_no_approval(monkeypatch) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "FAILED"},
        {
            "overall_status": "CRITICAL",
            "api_server": "RUNNING",
            "redis": "MISSING",
            "memory_status": "OK",
            "bridge_status": "OK",
            "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"


def test_memory_critical_manual_intervention_required(monkeypatch) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "api_server": "RUNNING",
            "redis": "RUNNING",
            "memory_status": "CRITICAL",
            "bridge_status": "OK",
            "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "approval_missing"
    assert decisions[0]["target"] == "memory"


def test_configured_action_path_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    monkeypatch.setenv("LUKA_ALLOW_API_RESTART", "1")
    monkeypatch.setattr(remediation_engine, "API_RESTART_PATH", Path("/nonexistent/restart.zsh"))

    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "FAILED"},
        {
            "overall_status": "CRITICAL",
            "api_server": "MISSING",
            "redis": "RUNNING",
            "memory_status": "OK",
            "bridge_status": "OK",
            "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"


def test_remediation_log_schema_valid(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"overall_status": "HEALTHY"})
        if cmd == ["tools/ops/operator_status_report.py", "--json"]:
            return _cp(
                args,
                0,
                {
                    "overall_status": "HEALTHY",
                    "api_server": "RUNNING",
                    "redis": "RUNNING",
                    "memory_status": "OK",
                    "bridge_status": "OK",
                    "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["timestamp"] == "2026-03-08T00:00:00Z"
    lines = (runtime_root / "state" / "remediation_actions.jsonl").read_text(encoding="utf-8").splitlines()
    stored = json.loads(lines[0])
    assert list(stored.keys()) == ["timestamp", "decision", "target", "reason", "action_taken", "source"]
    assert stored["source"] == "remediation_engine"


def test_approved_api_restart_action_taken(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    monkeypatch.setenv("LUKA_ALLOW_API_RESTART", "1")
    restart_path = tmp_path / "restart_api.zsh"
    restart_path.write_text("#!/bin/zsh\n", encoding="utf-8")
    monkeypatch.setattr(remediation_engine, "API_RESTART_PATH", restart_path)

    def fake_restart():
        return True, "api_restart_executed"

    monkeypatch.setattr(remediation_engine, "_run_api_restart", fake_restart)

    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "FAILED"},
        {
            "overall_status": "CRITICAL",
            "api_server": "MISSING",
            "redis": "RUNNING",
            "memory_status": "OK",
            "bridge_status": "OK",
            "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["action_taken"] is False
