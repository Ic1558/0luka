from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import remediation_engine, worker_recovery


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def test_healthy_bridge_workers_noop() -> None:
    decisions = worker_recovery.evaluate_worker_recovery(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "HEALTHY",
            "bridge_status": "OK",
            "details": {
                "bridge_consumer": {"status": "idle"},
                "bridge_watchdog": {"overall_status": "ok"},
                "bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"},
            },
            "errors": [],
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"


def test_bridge_failure_no_approval() -> None:
    decisions = worker_recovery.evaluate_worker_recovery(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "bridge_status": "FAILED",
            "details": {
                "bridge_consumer": {"status": "stalled"},
                "bridge_watchdog": {"overall_status": "failed"},
                "bridge_checks": {"consumer": "stalled", "inflight": "failed", "outbox": "ok"},
            },
            "errors": [],
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "approval_missing"
    assert decisions[0]["target"] == "bridge"


def test_bridge_failure_no_safe_recovery_path(monkeypatch) -> None:
    monkeypatch.setenv("LUKA_ALLOW_WORKER_RECOVERY", "1")
    monkeypatch.setattr(worker_recovery, "LAUNCHCTL_BIN", None)

    decisions = worker_recovery.evaluate_worker_recovery(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "bridge_status": "UNAVAILABLE",
            "details": {
                "bridge_consumer": None,
                "bridge_watchdog": None,
                "bridge_checks": {"consumer": "unavailable", "inflight": "unavailable", "outbox": "unavailable"},
            },
            "errors": [
                {"error": "telemetry_missing", "path": "/tmp/bridge_consumer.latest.json"},
                {"error": "telemetry_missing", "path": "/tmp/bridge_watchdog.latest.json"},
            ],
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "action_unavailable"
    assert decisions[0]["target"] == "bridge"


def test_approved_worker_recovery_path_action_taken(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LUKA_ALLOW_WORKER_RECOVERY", "1")
    monkeypatch.setattr(worker_recovery, "ALLOWED_WORKER_LABELS", ("com.0luka.bridge_watchdog",))

    def fake_run(args, cwd, capture_output, text, check, timeout):
        if args[:2] == [worker_recovery.LAUNCHCTL_BIN, "print"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="loaded", stderr="")
        if args[:3] == [worker_recovery.LAUNCHCTL_BIN, "kickstart", "-k"]:
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    decisions = worker_recovery.evaluate_worker_recovery(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "bridge_status": "FAILED",
            "details": {
                "bridge_consumer": {"status": "stalled"},
                "bridge_watchdog": {"overall_status": "failed"},
                "bridge_checks": {"consumer": "stalled", "inflight": "failed", "outbox": "ok"},
            },
            "errors": [],
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert [item["decision"] for item in decisions] == ["worker_recovery_started", "worker_recovery_finished"]
    assert all(item["action_taken"] is True for item in decisions)
    assert decisions[1]["reason"].startswith("worker_recovery_completed:")


def test_remediation_log_schema_valid_and_scoped(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(worker_recovery, "_utc_now", lambda: "2026-03-08T00:00:00Z")

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
                    "bridge_status": "OK",
                    "details": {
                        "bridge_consumer": {"status": "idle"},
                        "bridge_watchdog": {"overall_status": "ok"},
                        "bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"},
                    },
                    "errors": [],
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    decisions = worker_recovery.run_once(runtime_root=runtime_root)

    assert decisions[0]["timestamp"] == "2026-03-08T00:00:00Z"
    lines = (runtime_root / "state" / "remediation_actions.jsonl").read_text(encoding="utf-8").splitlines()
    stored = json.loads(lines[0])
    assert list(stored.keys()) == ["timestamp", "decision", "target", "reason", "action_taken", "source"]
    assert stored["source"] == "remediation_engine"
    assert sorted(str(path.relative_to(runtime_root)) for path in runtime_root.rglob("*") if path.is_file()) == [
        "state/remediation_actions.jsonl"
    ]


def test_remediation_engine_emits_worker_recovery_path(monkeypatch) -> None:
    monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (True, "bridge_status=FAILED"))
    monkeypatch.setattr(
        worker_recovery,
        "evaluate_worker_recovery",
        lambda runtime_status, operator_status, timestamp=None: [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "decision": "approval_missing",
                "target": "bridge",
                "reason": "bridge_status=FAILED; approval_missing:LUKA_ALLOW_WORKER_RECOVERY",
                "action_taken": False,
                "source": "remediation_engine",
            }
        ],
    )

    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "api_server": "RUNNING",
            "redis": "RUNNING",
            "memory_status": "OK",
            "bridge_status": "FAILED",
        },
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "approval_missing"
    assert decisions[0]["target"] == "bridge"
