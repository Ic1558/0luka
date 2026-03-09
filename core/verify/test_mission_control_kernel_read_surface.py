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

def test_kernel_status_endpoint_returns_json(client, monkeypatch):
    # Mock load_runtime_status to return a controlled payload
    monkeypatch.setattr(mission_control_server, "load_runtime_status", lambda: {
        "system_health": {"status": "OK"}
    })
    # Mock counts
    monkeypatch.setattr(mission_control_server, "load_verification_history", lambda limit: [
        {"trace_id": "t1", "verdict": "verified"}
    ])
    monkeypatch.setattr(mission_control_server, "load_guardian_history", lambda limit: [])
    
    # Mock environment
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", "/tmp/fake_root")
    
    response = client.get("/api/kernel/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["health"]["env_present"] is True
    assert data["health"]["suite_status"] == "ok"
    assert data["verification"]["recent_verification_count"] == 1
    assert "artifacts" in data

def test_verification_history_endpoint_returns_list(client, monkeypatch):
    mock_items = [
        {"trace_id": "trace_001", "verdict": "verified", "ts": "2026-03-09T10:00:00Z"},
        {"trace_id": "trace_002", "verdict": "failed", "ts": "2026-03-09T10:05:00Z"}
    ]
    monkeypatch.setattr(mission_control_server, "load_verification_history", lambda limit=50: mock_items)
    
    response = client.get("/api/kernel/verification_history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    assert data["items"][0]["trace_id"] == "trace_001"

def test_guardian_history_endpoint_returns_list(client, monkeypatch):
    mock_items = [
        {"ts": "2026-03-09T11:00:00Z", "action": "allow", "reason": "verified", "trace_id": "t1"}
    ]
    monkeypatch.setattr(mission_control_server, "load_guardian_history", lambda limit=50: mock_items)
    
    response = client.get("/api/kernel/guardian_history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["action"] == "allow"

def test_kernel_read_surface_is_read_only(client):
    # Verify that POST/PUT/DELETE are not allowed on these endpoints
    for method in ["post", "put", "delete"]:
        func = getattr(client, method)
        for endpoint in ["/api/kernel/status", "/api/kernel/verification_history", "/api/kernel/guardian_history"]:
            response = func(endpoint)
            # 405 Method Not Allowed or 404 depending on how Starlette handles unregistered methods
            assert response.status_code in [404, 405]
