from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


def test_remediation_history_endpoint_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_remediation_history",
        lambda lane=None, last=None: {"memory": {"attempts": 1}, "worker": {"attempts": 0}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []},
    )

    response = client.get("/api/remediation_history")

    assert response.status_code == 200
    assert response.json()["memory"]["attempts"] == 1


def test_empty_remediation_history_handled_safely(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_remediation_history",
        lambda lane=None, last=None: {"memory": {"attempts": 0, "lifecycle": []}, "worker": {"attempts": 0, "lifecycle": []}, "last_event": {"decision": None, "lane": None, "timestamp": None}, "timeline": [], "total_entries": 0},
    )

    response = client.get("/api/remediation_history")

    assert response.status_code == 200
    assert response.json()["total_entries"] == 0


def test_lane_filter_works(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)

    def fake_load(lane=None, last=None):
        assert lane == "memory"
        return {"memory": {"attempts": 2, "lifecycle": ["approval_missing"]}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []}

    monkeypatch.setattr(mission_control_server, "load_remediation_history", fake_load)

    response = client.get("/api/remediation_history?lane=memory")

    assert response.status_code == 200
    assert "worker" not in response.json()


def test_recent_timeline_entries_returned(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_remediation_history",
        lambda lane=None, last=None: {
            "memory": {"attempts": 2, "lifecycle": ["approval_missing", "cooldown_active"]},
            "worker": {"attempts": 0, "lifecycle": []},
            "last_event": {"decision": "cooldown_active", "lane": "memory", "timestamp": "2026-03-08T00:01:00Z"},
            "timeline": [
                {"timestamp": "2026-03-08T00:00:00Z", "decision": "approval_missing", "lane": "memory"},
                {"timestamp": "2026-03-08T00:01:00Z", "decision": "cooldown_active", "lane": "memory"},
            ],
        },
    )

    response = client.get("/api/remediation_history?last=5")

    assert response.status_code == 200
    assert len(response.json()["timeline"]) == 2
    assert response.json()["timeline"][-1]["decision"] == "cooldown_active"


def test_existing_endpoints_remain_functional(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "DEGRADED", "ledger_status": "VERIFIED", "memory_status": "CRITICAL", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": ["approval_missing"]}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []})

    assert client.get("/health").status_code == 200
    assert client.get("/api/operator_status").status_code == 200
    assert client.get("/api/runtime_status").status_code == 200
    assert client.get("/api/activity").status_code == 200
    assert client.get("/").status_code == 200
