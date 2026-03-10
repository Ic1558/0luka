from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


def test_approval_history_endpoint_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_approval_history",
        lambda lane=None, last=None: {
            "events": [
                {
                    "timestamp": "2026-03-08T00:00:00Z",
                    "lane": "memory_recovery",
                    "action": "approve",
                    "actor": "Boss",
                    "approved": True,
                    "expires_at": None,
                    "source": "approval_write",
                }
            ],
            "last_event": {
                "timestamp": "2026-03-08T00:00:00Z",
                "lane": "memory_recovery",
                "action": "approve",
                "actor": "Boss",
            },
            "total_entries": 1,
        },
    )

    response = client.get("/api/approval_history")

    assert response.status_code == 200
    assert response.json()["events"][0]["action"] == "approve"


def test_empty_approval_history_handled_safely(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_approval_history",
        lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0},
    )

    response = client.get("/api/approval_history")

    assert response.status_code == 200
    assert response.json()["events"] == []
    assert response.json()["total_entries"] == 0


def test_approval_history_lane_filter_works(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)

    def fake_load(lane=None, last=None):
        assert lane == "memory_recovery"
        return {"events": [], "last_event": None, "total_entries": 0}

    monkeypatch.setattr(mission_control_server, "load_approval_history", fake_load)

    response = client.get("/api/approval_history?lane=memory_recovery")

    assert response.status_code == 200


def test_recent_approval_history_entries_returned(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_approval_history",
        lambda lane=None, last=None: {
            "events": [
                {
                    "timestamp": "2026-03-08T00:00:00Z",
                    "lane": "memory_recovery",
                    "action": "approve",
                    "actor": "Boss",
                    "approved": True,
                    "expires_at": None,
                    "source": "approval_write",
                },
                {
                    "timestamp": "2026-03-08T00:05:00Z",
                    "lane": "memory_recovery",
                    "action": "set_expiry",
                    "actor": "Boss",
                    "approved": True,
                    "expires_at": "2026-03-08T01:00:00Z",
                    "source": "approval_write",
                },
            ],
            "last_event": {
                "timestamp": "2026-03-08T00:05:00Z",
                "lane": "memory_recovery",
                "action": "set_expiry",
                "actor": "Boss",
            },
            "total_entries": 2,
        },
    )

    response = client.get("/api/approval_history?last=5")

    assert response.status_code == 200
    assert len(response.json()["events"]) == 2
    assert response.json()["last_event"]["action"] == "set_expiry"


def test_existing_endpoints_remain_functional(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "DEGRADED", "ledger_status": "VERIFIED", "memory_status": "CRITICAL", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": ["approval_missing"]}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []})
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda lane=None: {"lanes": {"memory_recovery": {"status": "approval_required", "reason": "env_gate_missing", "approval_state": "present", "expires_at": None, "expired": False, "expiring_soon": False}}})
    monkeypatch.setattr(mission_control_server, "load_approval_history", lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0})

    assert client.get("/health").status_code == 200
    assert client.get("/api/operator_status").status_code == 200
    assert client.get("/api/runtime_status").status_code == 200
    assert client.get("/api/activity").status_code == 200
    assert client.get("/api/approval_history").status_code == 200
    assert client.get("/").status_code == 200
