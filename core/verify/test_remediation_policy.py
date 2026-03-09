from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import memory_recovery, remediation_engine, worker_recovery


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def _fake_status_runner(runtime_payload: dict[str, object], operator_payload: dict[str, object]):
    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, runtime_payload)
        if cmd == ["tools/ops/operator_status_report.py", "--json"]:
            return _cp(args, 0, operator_payload)
        raise AssertionError(args)

    return fake_run


def test_healthy_system_noop(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "HEALTHY",
                "memory_status": "OK",
                "bridge_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["decision"] == "noop"
    state = json.loads((runtime_root / "state" / "remediation_state.json").read_text(encoding="utf-8"))
    assert state["memory_recovery_attempts"] == 0
    assert state["worker_recovery_attempts"] == 0


def test_memory_failure_first_attempt_uses_priority(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "DEGRADED",
                "memory_status": "CRITICAL",
                "bridge_status": "FAILED",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "stalled", "inflight": "failed", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (True, "bridge_status=FAILED"))
    monkeypatch.setattr(
        memory_recovery,
        "evaluate_memory_recovery",
        lambda runtime_status, operator_status, timestamp=None, runtime_root=None: [
            {
                "timestamp": timestamp,
                "decision": "memory_recovery_started",
                "target": "memory",
                "reason": "started",
                "action_taken": True,
                "source": "remediation_engine",
            },
            {
                "timestamp": timestamp,
                "decision": "memory_recovery_finished",
                "target": "memory",
                "reason": "finished",
                "action_taken": True,
                "source": "remediation_engine",
            },
        ],
    )
    monkeypatch.setattr(worker_recovery, "evaluate_worker_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("worker lane should not run")))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert [item["decision"] for item in decisions] == ["memory_recovery_started", "memory_recovery_finished", "remediation_recovered"]
    state = json.loads((runtime_root / "state" / "remediation_state.json").read_text(encoding="utf-8"))
    assert state["memory_recovery_attempts"] == 0
    assert state["worker_recovery_attempts"] == 0


def test_retry_attempt_after_cooldown(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "remediation_state.json").write_text(
        json.dumps(
            {
                "memory_recovery_attempts": 1,
                "worker_recovery_attempts": 0,
                "memory_last_attempt": "2026-03-07T23:55:00Z",
                "worker_last_attempt": None,
                "last_attempt": "2026-03-07T23:55:00Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "DEGRADED",
                "memory_status": "CRITICAL",
                "bridge_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    monkeypatch.setattr(
        memory_recovery,
        "evaluate_memory_recovery",
        lambda runtime_status, operator_status, timestamp=None, runtime_root=None: [
            {
                "timestamp": timestamp,
                "decision": "memory_recovery_started",
                "target": "memory",
                "reason": "started",
                "action_taken": True,
                "source": "remediation_engine",
            },
            {
                "timestamp": timestamp,
                "decision": "memory_recovery_finished",
                "target": "memory",
                "reason": "finished",
                "action_taken": True,
                "source": "remediation_engine",
            },
        ],
    )

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["decision"] == "memory_recovery_started"
    state = json.loads((state_dir / "remediation_state.json").read_text(encoding="utf-8"))
    assert state["memory_recovery_attempts"] == 0


def test_cooldown_active(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "remediation_state.json").write_text(
        json.dumps(
            {
                "memory_recovery_attempts": 1,
                "worker_recovery_attempts": 0,
                "memory_last_attempt": "2026-03-07T23:59:30Z",
                "worker_last_attempt": None,
                "last_attempt": "2026-03-07T23:59:30Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "DEGRADED",
                "memory_status": "CRITICAL",
                "bridge_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    monkeypatch.setattr(memory_recovery, "evaluate_memory_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cooldown should block recovery")))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["decision"] == "cooldown_active"
    assert decisions[0]["target"] == "memory"


def test_escalation_triggered(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "remediation_state.json").write_text(
        json.dumps(
            {
                "memory_recovery_attempts": 3,
                "worker_recovery_attempts": 0,
                "memory_last_attempt": "2026-03-07T23:59:30Z",
                "worker_last_attempt": None,
                "last_attempt": "2026-03-07T23:59:30Z",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "DEGRADED",
                "memory_status": "CRITICAL",
                "bridge_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
    monkeypatch.setattr(memory_recovery, "evaluate_memory_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("escalation should block recovery")))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["decision"] == "remediation_escalated"
    assert decisions[0]["target"] == "memory"


def test_remediation_log_schema_valid(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        _fake_status_runner(
            {"overall_status": "HEALTHY"},
            {
                "overall_status": "HEALTHY",
                "memory_status": "OK",
                "bridge_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                "errors": [],
            },
        ),
    )
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))

    decisions = remediation_engine.run_once(runtime_root=runtime_root)

    assert decisions[0]["timestamp"] == "2026-03-08T00:00:00Z"
    stored = json.loads((runtime_root / "state" / "remediation_actions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert list(stored.keys()) == ["timestamp", "decision", "target", "reason", "action_taken", "source"]
    state = json.loads((runtime_root / "state" / "remediation_state.json").read_text(encoding="utf-8"))
    assert list(state.keys()) == [
        "last_attempt",
        "memory_last_attempt",
        "memory_recovery_attempts",
        "worker_last_attempt",
        "worker_recovery_attempts",
    ]
