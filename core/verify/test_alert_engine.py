from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.alert_engine import evaluate_alerts, run_once


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def _write_activity(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def test_memory_critical_produces_critical_alert() -> None:
    alerts = evaluate_alerts(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "DEGRADED",
            "memory_status": "CRITICAL",
            "ledger_status": "VERIFIED",
            "redis": "RUNNING",
            "api_server": "RUNNING",
            "bridge_status": "OK",
        },
        [{"ts_utc": "2026-03-08T00:00:00Z", "action": "bridge_heartbeat"}],
        timestamp="2026-03-08T00:00:01Z",
    )

    memory_alert = next(alert for alert in alerts if alert["component"] == "memory")

    assert memory_alert["severity"] == "CRITICAL"
    assert memory_alert["message"].startswith("memory_status=CRITICAL")


def test_redis_down_produces_critical_alert() -> None:
    alerts = evaluate_alerts(
        {"overall_status": "HEALTHY"},
        {
            "overall_status": "CRITICAL",
            "memory_status": "OK",
            "ledger_status": "VERIFIED",
            "redis": "MISSING",
            "api_server": "RUNNING",
            "bridge_status": "OK",
        },
        [],
        timestamp="2026-03-08T00:00:01Z",
    )

    redis_alert = next(alert for alert in alerts if alert["component"] == "redis")

    assert redis_alert["severity"] == "CRITICAL"
    assert redis_alert["message"] == "redis=MISSING"


def test_healthy_runtime_produces_no_alert(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(observability_root))
    _write_activity(
        observability_root / "logs" / "activity_feed.jsonl",
        [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}],
    )

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
                    "memory_status": "OK",
                    "ledger_status": "VERIFIED",
                    "redis": "RUNNING",
                    "api_server": "RUNNING",
                    "bridge_status": "OK",
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    alerts = run_once(runtime_root=runtime_root)

    assert alerts == []
    assert not (runtime_root / "state" / "alerts.jsonl").exists()


def test_alert_json_schema_validity(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("LUKA_OBSERVABILITY_ROOT", str(observability_root))
    _write_activity(
        observability_root / "logs" / "activity_feed.jsonl",
        [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}],
    )

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"overall_status": "HEALTHY"})
        if cmd == ["tools/ops/operator_status_report.py", "--json"]:
            return _cp(
                args,
                0,
                {
                    "overall_status": "DEGRADED",
                    "memory_status": "CRITICAL",
                    "ledger_status": "VERIFIED",
                    "redis": "RUNNING",
                    "api_server": "RUNNING",
                    "bridge_status": "OK",
                },
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("tools.ops.alert_engine._utc_now", lambda: "2026-03-08T00:00:01Z")

    alerts = run_once(runtime_root=runtime_root)

    assert len(alerts) == 2
    first = alerts[0]
    assert list(first.keys()) == ["timestamp", "severity", "component", "message", "source"]
    assert first["timestamp"] == "2026-03-08T00:00:01Z"
    assert first["source"] == "alert_engine"

    lines = (runtime_root / "state" / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
    stored = json.loads(lines[0])
    assert stored == first
