from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interface.operator import mission_control_server


def test_nominal_preview_response(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"drift_count": 0})
    monkeypatch.setattr(
        mission_control_server,
        "classify_once",
        lambda **_: {"type": "nominal"},
    )

    response = client.get("/api/decision_preview")

    assert response.status_code == 200
    assert response.json() == {
        "classification": "nominal",
        "inputs": {
            "operator_status": {"ok": True},
            "runtime_status": {"ok": True},
            "policy_drift": {"drift_count": 0},
        },
    }


def test_drift_detected_preview_response(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": False})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"drift_count": 0})
    monkeypatch.setattr(
        mission_control_server,
        "classify_once",
        lambda **_: {"type": "drift_detected"},
    )

    response = client.get("/api/decision_preview")

    assert response.status_code == 200
    assert response.json()["classification"] == "drift_detected"


def test_missing_input_returns_classification_null(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True})

    def raise_missing() -> dict[str, object]:
        raise RuntimeError("missing")

    monkeypatch.setattr(mission_control_server, "load_policy_drift", raise_missing)

    response = client.get("/api/decision_preview")

    assert response.status_code == 200
    assert response.json() == {
        "classification": None,
        "inputs": {
            "operator_status": {"ok": True},
            "runtime_status": {"ok": True},
            "policy_drift": None,
        },
    }


def test_endpoint_is_read_only_json_surface(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"drift_count": 0})
    monkeypatch.setattr(
        mission_control_server,
        "classify_once",
        lambda **_: {"type": "nominal"},
    )

    response = client.get("/api/decision_preview")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["classification"] == "nominal"


def test_no_persistence_side_effects_are_attempted(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"drift_count": 0})
    monkeypatch.setattr(
        mission_control_server,
        "classify_once",
        lambda **_: {"type": "nominal"},
    )

    def fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("unexpected side effect")

    monkeypatch.setattr(mission_control_server, "apply_approval_action", fail)
    monkeypatch.setattr(mission_control_server, "enqueue_remediation_queue", fail)

    response = client.get("/api/decision_preview")

    assert response.status_code == 200
    assert response.json()["classification"] == "nominal"
