from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


def _write_alerts(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def test_alerts_endpoint_returns_valid_json(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    _write_alerts(
        runtime_root / "state" / "alerts.jsonl",
        [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "severity": "CRITICAL",
                "component": "memory",
                "message": "memory_status=CRITICAL",
                "source": "alert_engine",
            }
        ],
    )
    client = TestClient(mission_control_server.app)

    response = client.get("/api/alerts")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert payload["alerts"][0]["component"] == "memory"


def test_alerts_are_parsed_from_alerts_jsonl(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    _write_alerts(
        runtime_root / "state" / "alerts.jsonl",
        [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "severity": "WARNING",
                "component": "runtime",
                "message": "operator overall_status=DEGRADED",
                "source": "alert_engine",
            },
            {
                "timestamp": "2026-03-08T00:00:05Z",
                "severity": "CRITICAL",
                "component": "redis",
                "message": "redis=MISSING",
                "source": "alert_engine",
            },
        ],
    )

    alerts = mission_control_server.load_alerts(limit=10)

    assert len(alerts) == 2
    assert alerts[-1]["component"] == "redis"


def test_ui_loads_without_error(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"overall_status": "DEGRADED", "ledger_status": "VERIFIED", "memory_status": "CRITICAL", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [{"timestamp": "2026-03-08T00:00:00Z", "severity": "CRITICAL", "component": "memory", "message": "memory_status=CRITICAL", "source": "alert_engine"}])

    response = client.get("/")

    assert response.status_code == 200
    assert "Mission Control" in response.text
    assert "Alerts" in response.text
    assert "setInterval(refreshAlerts, 5000)" in response.text
