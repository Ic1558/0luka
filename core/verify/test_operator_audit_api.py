from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


def test_audit_endpoints_return_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_remediation_audit_entries", lambda last=100: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "timeline": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_approval_log_entries", lambda last=100: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_runtime_decisions", lambda last=100: {"ok": True, "entries": []})

    for path in ("/api/remediation_history", "/api/approval_log", "/api/runtime_decisions"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert isinstance(payload["entries"], list)


def test_entries_parse_correctly(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    state = runtime_root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "remediation_history.jsonl").write_text(
        json.dumps({"timestamp": "2026-03-08T00:00:00Z", "lane": "worker_recovery", "decision": "cooldown_active", "result": "blocked"}) + "\n",
        encoding="utf-8",
    )
    (state / "approval_actions.jsonl").write_text(
        json.dumps({"timestamp": "2026-03-08T00:01:00Z", "lane": "memory_recovery", "action": "approve", "actor": "Boss"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    remediation = mission_control_server.load_remediation_audit_entries(last=10)
    approval = mission_control_server.load_approval_log_entries(last=10)
    decisions = mission_control_server.load_runtime_decisions(last=10)

    assert remediation["entries"][0]["result"] == "blocked"
    assert approval["entries"][0]["action"] == "approve"
    assert decisions["entries"][0]["decision"] == "cooldown_active"


def test_no_runtime_state_mutation(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    state = runtime_root / "state"
    state.mkdir(parents=True, exist_ok=True)
    history_path = state / "remediation_history.jsonl"
    approval_path = state / "approval_actions.jsonl"
    history_path.write_text(json.dumps({"decision": "noop"}) + "\n", encoding="utf-8")
    approval_path.write_text(json.dumps({"action": "approve"}) + "\n", encoding="utf-8")
    before = {
        str(history_path): history_path.read_text(encoding="utf-8"),
        str(approval_path): approval_path.read_text(encoding="utf-8"),
    }
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    mission_control_server.load_remediation_audit_entries(last=10)
    mission_control_server.load_approval_log_entries(last=10)
    mission_control_server.load_runtime_decisions(last=10)

    after = {
        str(history_path): history_path.read_text(encoding="utf-8"),
        str(approval_path): approval_path.read_text(encoding="utf-8"),
    }
    assert before == after


def test_existing_apis_remain_compatible(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "HEALTHY", "ledger_status": "VERIFIED", "memory_status": "OK", "api_server": "RUNNING", "redis": "RUNNING", "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}}})
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 1}})
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_history", lambda lane=None, last=None: {"memory": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []}, "timeline": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda lane=None: {"lanes": {}})
    monkeypatch.setattr(mission_control_server, "load_approval_history", lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_approval_presets", lambda: {"presets": []})
    monkeypatch.setattr(mission_control_server, "load_approval_expiry", lambda: {"lanes": []})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"checks": {}})
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", lambda: {"items": []})
    monkeypatch.setattr(mission_control_server, "load_remediation_audit_entries", lambda last=20: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_approval_log_entries", lambda last=20: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_runtime_decisions", lambda last=20: {"ok": True, "entries": []})

    assert client.get("/health").status_code == 200
    assert client.get("/api/runtime_status").status_code == 200
    assert client.get("/api/remediation_history").status_code == 200
    assert client.get("/api/approval_log").status_code == 200
    assert client.get("/api/runtime_decisions").status_code == 200
    assert client.get("/").status_code == 200
