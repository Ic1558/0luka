from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(mission_control_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_operator_status_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "CRITICAL"})

    response = client.get("/api/operator_status")

    assert response.status_code == 200
    assert response.json()["overall_status"] == "CRITICAL"


def test_runtime_status_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_runtime_status",
        lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}},
    )

    response = client.get("/api/runtime_status")

    assert response.status_code == 200
    assert response.json()["system_health"]["status"] == "HEALTHY"


def test_activity_endpoint_returns_list(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_activity_entries",
        lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}],
    )

    response = client.get("/api/activity")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert response.json()[0]["action"] == "proof_export"
