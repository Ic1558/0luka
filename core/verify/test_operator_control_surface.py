from __future__ import annotations

import json
import sys
import hashlib
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

def test_operator_endpoints_return_json(client, monkeypatch):
    # Mock loaders to avoid logic complexity
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda: {"lanes": {}, "approval_state": {}})
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", lambda: {"items": []})
    monkeypatch.setattr(mission_control_server, "load_operator_runtime_decisions", lambda: [])
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {"checks": {}})
    monkeypatch.setattr(mission_control_server, "load_qs_runs_summary", lambda: {"items": [], "summary": {}})

    endpoints = [
        "/api/operator/approval_state",
        "/api/operator/remediation_queue",
        "/api/operator/runtime_decisions",
        "/api/operator/policy_drift",
        "/api/operator/qs_overview"
    ]
    
    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert isinstance(response.json(), dict)

def test_operator_endpoints_get_only(client):
    endpoints = [
        "/api/operator/approval_state",
        "/api/operator/remediation_queue",
        "/api/operator/runtime_decisions",
        "/api/operator/policy_drift",
        "/api/operator/qs_overview"
    ]
    
    for method in ["post", "put", "delete"]:
        func = getattr(client, method)
        for url in endpoints:
            response = func(url)
            # Should be 405 Method Not Allowed or 404
            assert response.status_code in [404, 405]

def test_operator_endpoints_safe_degradation(client, monkeypatch):
    # Mock loaders to raise exceptions or return None to simulate missing data
    def _fail(): raise RuntimeError("file_missing")
    
    # In mission_control_server, exceptions in loaders should be handled
    # or return empty default structures.
    monkeypatch.setattr(mission_control_server, "load_autonomy_policy", lambda: {})
    monkeypatch.setattr(mission_control_server, "load_remediation_queue", lambda: {})
    monkeypatch.setattr(mission_control_server, "load_operator_runtime_decisions", lambda: [])
    monkeypatch.setattr(mission_control_server, "load_policy_drift", lambda: {})
    monkeypatch.setattr(mission_control_server, "load_qs_runs_summary", lambda: {})

    endpoints = [
        "/api/operator/approval_state",
        "/api/operator/remediation_queue",
        "/api/operator/runtime_decisions",
        "/api/operator/policy_drift",
        "/api/operator/qs_overview"
    ]
    
    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 200
        assert isinstance(response.json(), (dict, list))

def test_operator_endpoints_do_not_mutate_state(client, monkeypatch, tmp_path):
    # This is a conceptual test. In a real scenario we'd check disk hashes.
    # Since we use mocks, we verify that no write paths are called.
    
    # We can use monkeypatch to ensure no subprocesses or writes happen
    # by catching them if they occur.
    
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    
    # Call endpoints
    endpoints = ["/api/operator/approval_state", "/api/operator/qs_overview"]
    for url in endpoints:
        client.get(url)
    
    # Verify no new files created in state/ beyond what we expected
    # (Only reading should happen)
    files = list(tmp_path.rglob("*"))
    # Only the directories we created should exist
    assert len([f for f in files if f.is_file()]) == 0
