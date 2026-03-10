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


def test_proof_artifacts_endpoint_returns_inventory(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_proof_artifacts",
        lambda limit=50: {
            "artifacts": [
                {
                    "artifact_type": "proof_pack",
                    "name": "pack_001",
                    "path": "/tmp/proof_packs/pack_001",
                    "manifest_present": True,
                    "mtime_utc": 1741392000.0,
                }
            ],
            "total_entries": 1,
        },
    )

    response = client.get("/api/proof_artifacts?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_entries"] == 1
    assert payload["artifacts"][0]["artifact_type"] == "proof_pack"
    assert payload["artifacts"][0]["manifest_present"] is True


def test_qs_runs_endpoint_returns_list(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_runs",
        lambda limit=100: {"ok": True, "runs": [{"run_id": "qs_run_1"}], "total_entries": 1},
    )

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    assert response.json()["runs"][0]["run_id"] == "qs_run_1"


def test_qs_runs_endpoint_safe_empty(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_runs",
        lambda limit=100: {"ok": True, "runs": [], "total_entries": 0},
    )

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    assert response.json()["runs"] == []


def test_qs_run_detail_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_run",
        lambda run_id: {"run_id": run_id, "status": "completed"} if run_id == "valid_id" else None,
    )

    response = client.get("/api/qs_runs/valid_id")

    assert response.status_code == 200
    assert response.json()["run_id"] == "valid_id"


def test_qs_run_detail_endpoint_returns_404(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_run",
        lambda run_id: None,
    )

    response = client.get("/api/qs_runs/invalid_id")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
