from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interface.operator import mission_control_server

@pytest.fixture
def client():
    return TestClient(mission_control_server.app)

def test_dashboard_endpoint_returns_json(client, monkeypatch):
    # Mock all loaders
    monkeypatch.setattr(mission_control_server, "load_kernel_status", lambda: {"status": "ok"})
    monkeypatch.setattr(mission_control_server, "load_verification_history", lambda limit: [])
    monkeypatch.setattr(mission_control_server, "load_guardian_history", lambda limit: [])
    monkeypatch.setattr(mission_control_server, "load_operator_runtime_decisions", lambda limit: [])
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", lambda: {"items": []})
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda: {"lanes": {}, "approval_state": {}})
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"checks": {}})
    monkeypatch.setattr(mission_control_server, "load_qs_runs_summary", lambda: {"summary": {}, "items": []})

    response = client.get("/api/operator/dashboard")
    assert response.status_code == 200
    data = response.json()
    
    expected_keys = {
        "kernel", "verification", "guardian", "runtime_decisions",
        "remediation_queue", "approval_state", "policy_drift", "qs_overview"
    }
    assert set(data.keys()) == expected_keys

def test_dashboard_safe_degradation(client, monkeypatch):
    # Simulate partial loader failures
    def _fail(*args, **kwargs): raise RuntimeError("aggregator_failure")
    
    # load_dashboard_state wraps some in try/except, 
    # others (kernel, verification, guardian, decisions, policy_drift) 
    # depend on internal loader robustness or mission_control_server's existing safety.
    
    monkeypatch.setattr(mission_control_server, "load_qs_runs_summary", _fail)
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", _fail)
    
    response = client.get("/api/operator/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "qs_overview" in data
    assert data["qs_overview"]["recent_items"] == []
    assert data["remediation_queue"] == []

def test_dashboard_ordering_limits(client, monkeypatch):
    # Create 30 mock QS runs
    mock_qs = {
        "summary": {"total_runs": 30},
        "items": [{"run_id": f"run_{i:03d}"} for i in range(30)]
    }
    monkeypatch.setattr(mission_control_server, "load_qs_runs_summary", lambda: mock_qs)
    
    # Create 60 mock decisions
    mock_decisions = [{"timestamp": i} for i in range(60)]
    monkeypatch.setattr(mission_control_server, "load_operator_runtime_decisions", lambda limit: mock_decisions[:limit])

    response = client.get("/api/operator/dashboard")
    data = response.json()
    
    assert len(data["qs_overview"]["recent_items"]) == 20
    assert len(data["runtime_decisions"]) == 50
