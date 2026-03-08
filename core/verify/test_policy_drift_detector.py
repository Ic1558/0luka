from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import policy_drift_detector


def _write_state(runtime_root: Path, payload: dict) -> None:
    path = runtime_root / "state" / "approval_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _append_action(runtime_root: Path, row: dict) -> None:
    path = runtime_root / "state" / "approval_actions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_no_drift_detected(tmp_path, monkeypatch) -> None:
    _write_state(
        tmp_path,
        {
            "memory_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "worker_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "api_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "redis_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
        },
    )
    monkeypatch.setattr(
        policy_drift_detector.autonomy_policy,
        "evaluate_policy",
        lambda runtime_root=None: {
            "ok": True,
            "lanes": {
                "memory_recovery": {"status": "approval_required", "env_gate_present": False},
                "worker_recovery": {"status": "approval_required", "env_gate_present": False},
                "api_recovery": {"status": "approval_required", "env_gate_present": False},
                "redis_recovery": {"status": "unavailable", "env_gate_present": False},
            },
        },
    )
    payload = policy_drift_detector.detect_drift(runtime_root=tmp_path)
    assert payload["ok"] is True
    assert payload["drift_count"] == 0


def test_approval_log_mismatch_detected(tmp_path, monkeypatch) -> None:
    _write_state(
        tmp_path,
        {
            "memory_recovery": {"approved": True, "approved_by": "Boss", "approved_at": "2026-03-08T05:00:00Z", "expires_at": None},
            "worker_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "api_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "redis_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
        },
    )
    _append_action(
        tmp_path,
        {
            "timestamp": "2026-03-08T06:00:00Z",
            "lane": "memory_recovery",
            "action": "revoke",
            "actor": "Boss",
            "approved": False,
            "expires_at": None,
            "source": "approval_write",
        },
    )
    monkeypatch.setattr(
        policy_drift_detector.autonomy_policy,
        "evaluate_policy",
        lambda runtime_root=None: {"ok": True, "lanes": {}},
    )
    payload = policy_drift_detector.detect_drift(runtime_root=tmp_path)
    assert payload["ok"] is False
    assert any(issue["type"] == "approval_log_drift" for issue in payload["issues"])


def test_expired_approval_detected(tmp_path, monkeypatch) -> None:
    _write_state(
        tmp_path,
        {
            "memory_recovery": {"approved": True, "approved_by": "Boss", "approved_at": "2026-03-08T05:00:00Z", "expires_at": "2026-03-08T05:01:00Z"},
            "worker_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "api_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "redis_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
        },
    )
    monkeypatch.setattr(
        policy_drift_detector.autonomy_policy,
        "evaluate_policy",
        lambda runtime_root=None: {"ok": True, "lanes": {}},
    )
    payload = policy_drift_detector.detect_drift(runtime_root=tmp_path)
    assert payload["ok"] is False
    assert any(issue["type"] == "expiry_drift" for issue in payload["issues"])


def test_unknown_lane_detected(tmp_path, monkeypatch) -> None:
    _write_state(
        tmp_path,
        {
            "memory_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "worker_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "api_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "redis_recovery": {"approved": False, "approved_by": None, "approved_at": None, "expires_at": None},
            "unknown_lane": {"approved": True},
        },
    )
    monkeypatch.setattr(
        policy_drift_detector.autonomy_policy,
        "evaluate_policy",
        lambda runtime_root=None: {"ok": True, "lanes": {}},
    )
    payload = policy_drift_detector.detect_drift(runtime_root=tmp_path)
    assert payload["ok"] is False
    assert any(issue["type"] == "lane_registry_drift" for issue in payload["issues"])


def test_api_endpoint_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_policy_drift",
        lambda: {
            "ok": True,
            "drift_count": 0,
            "checks": {
                "approval_log_consistency": "OK",
                "expiry_consistency": "OK",
                "env_gate_consistency": "OK",
                "lane_registry_consistency": "OK",
            },
            "issues": [],
        },
    )
    response = client.get("/api/policy_drift")
    assert response.status_code == 200
    assert response.json()["drift_count"] == 0


def test_mission_control_panel_loads(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "DEGRADED", "ledger_status": "VERIFIED", "memory_status": "CRITICAL", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": ["approval_missing"]}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []})
    monkeypatch.setattr(mission_control_server, "load_approval_history", lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_approval_presets", lambda: {"ok": True, "presets": []})
    monkeypatch.setattr(mission_control_server, "load_approval_expiry", lambda: {"ok": True, "timestamp": "2026-03-08T06:00:00Z", "lanes": []})
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda lane=None: {"lanes": {"memory_recovery": {"status": "approval_required", "reason": "env_gate_missing", "approval_state": "present", "expires_at": None, "expired": False, "expiring_soon": False}}})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"ok": True, "drift_count": 0, "checks": {"approval_log_consistency": "OK", "expiry_consistency": "OK", "env_gate_consistency": "OK", "lane_registry_consistency": "OK"}, "issues": []})
    response = client.get("/")
    assert response.status_code == 200
    assert "Policy Consistency" in response.text
