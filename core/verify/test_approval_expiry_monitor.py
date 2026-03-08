from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import approval_expiry_monitor


def _write_state(runtime_root: Path, payload: dict) -> None:
    path = runtime_root / "state" / "approval_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_state_returns_ok_with_default_lanes(tmp_path) -> None:
    payload = approval_expiry_monitor.evaluate_expiry(runtime_root=tmp_path)
    assert payload["ok"] is True
    assert len(payload["lanes"]) == 4
    assert all(row["status"] == "OK" for row in payload["lanes"])


def test_detects_expired_and_expiring_soon(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    expired_ts = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    soon_ts = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-08T05:00:00Z",
                "expires_at": expired_ts,
            },
            "worker_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-08T05:00:00Z",
                "expires_at": soon_ts,
            },
        },
    )
    payload = approval_expiry_monitor.evaluate_expiry(runtime_root=tmp_path)
    by_lane = {row["lane"]: row for row in payload["lanes"]}
    assert by_lane["memory_recovery"]["status"] == "EXPIRED"
    assert by_lane["worker_recovery"]["status"] == "EXPIRING_SOON"


def test_api_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_approval_expiry",
        lambda: {
            "ok": True,
            "timestamp": "2026-03-08T06:00:00Z",
            "lanes": [
                {
                    "lane": "memory_recovery",
                    "actor": "Boss",
                    "expires_at": "2026-03-08T07:00:00Z",
                    "status": "EXPIRING_SOON",
                    "expired": False,
                    "expiring_soon": True,
                    "approval_present": True,
                }
            ],
        },
    )
    response = client.get("/api/approval_expiry")
    assert response.status_code == 200
    assert response.json()["lanes"][0]["status"] == "EXPIRING_SOON"


def test_existing_endpoints_remain_functional(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "DEGRADED", "ledger_status": "VERIFIED", "memory_status": "CRITICAL", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": ["approval_missing"]}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []})
    monkeypatch.setattr(mission_control_server, "load_approval_history", lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_approval_presets", lambda: {"ok": True, "presets": []})
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda lane=None: {"lanes": {"memory_recovery": {"status": "approval_required", "reason": "env_gate_missing", "approval_state": "present", "expires_at": None, "expired": False, "expiring_soon": False}}})
    monkeypatch.setattr(mission_control_server, "load_approval_expiry", lambda: {"ok": True, "timestamp": "2026-03-08T06:00:00Z", "lanes": []})

    assert client.get("/health").status_code == 200
    assert client.get("/api/operator_status").status_code == 200
    assert client.get("/api/runtime_status").status_code == 200
    assert client.get("/api/activity").status_code == 200
    assert client.get("/api/approval_expiry").status_code == 200
    assert client.get("/").status_code == 200
