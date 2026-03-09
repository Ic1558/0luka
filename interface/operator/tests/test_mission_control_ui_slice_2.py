from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interface.operator import mission_control_server


def _html_text() -> str:
    return (ROOT / "interface" / "operator" / "templates" / "mission_control.html").read_text(encoding="utf-8")


def test_run_list_rendering_contract_present() -> None:
    html = _html_text()

    assert "Run Detail Panel" in html
    assert "/api/qs_runs/" in html
    assert "renderRunList" in html
    assert "loadRunDetail" in html
    assert "run-state-running" in html
    assert "run-state-blocked" in html
    assert "run-state-awaiting_approval" in html
    assert "run-state-completed" in html


def test_empty_state_behavior_present() -> None:
    html = _html_text()

    assert "No active QS runs detected." in html
    assert "System is idle." in html


def test_error_fallback_behavior_present() -> None:
    html = _html_text()

    assert "Mission Control API unreachable" in html
    assert "Check opal_api_server status" in html
    assert "/health" in html
    assert "FETCH_TIMEOUT_MS = 3000" in html
    assert "POLL_INTERVAL_MS = 10000" in html
    assert "MAX_BACKOFF_MS = 60000" in html


def test_root_route_contains_operator_trace_panel(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)

    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "HEALTHY"})
    monkeypatch.setattr(
        mission_control_server,
        "load_runtime_status",
        lambda: {"ok": True, "system_health": {"status": "OK"}, "proof_pack": {"epoch_id": 1}},
    )
    monkeypatch.setattr(mission_control_server, "load_activity_entries", lambda limit=50: [])
    monkeypatch.setattr(mission_control_server, "load_alerts", lambda limit=100: [])
    monkeypatch.setattr(
        mission_control_server,
        "load_remediation_history",
        lambda lane=None, last=None: {
            "memory": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []},
            "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []},
            "timeline": [],
            "last_event": None,
            "total_entries": 0,
        },
    )
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda lane=None: {"lanes": {}, "approval_state": {}})
    monkeypatch.setattr(mission_control_server, "load_approval_history", lambda lane=None, last=None: {"events": [], "last_event": None, "total_entries": 0})
    monkeypatch.setattr(mission_control_server, "load_approval_presets", lambda: {"presets": []})
    monkeypatch.setattr(mission_control_server, "load_approval_expiry", lambda: {"lanes": []})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"checks": {}})
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", lambda: {"items": []})
    monkeypatch.setattr(mission_control_server, "load_remediation_audit_entries", lambda last=20: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_approval_log_entries", lambda last=20: {"ok": True, "entries": []})
    monkeypatch.setattr(mission_control_server, "load_runtime_decisions", lambda last=20: {"ok": True, "entries": []})

    response = client.get("/")

    assert response.status_code == 200
    assert "Operator Trace" in response.text
    assert "QS Run Operations" in response.text
    assert "No active QS runs detected." in response.text

