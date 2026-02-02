"""
Integration Tests for NLP Control Plane API
============================================
"""

import pytest
from fastapi.testclient import TestClient
import uuid

from ..app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def session_id():
    """Generate valid session ID."""
    return str(uuid.uuid4())


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "nlp_control_plane"

    def test_health(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestChatEndpoints:
    """Test chat control plane endpoints."""

    def test_preview_returns_structure(self, client, session_id):
        """Test /preview returns correct structure."""
        response = client.post(
            "/api/v1/chat/preview",
            json={
                "raw_input": "liam check status",
                "channel": "terminal",
                "session_id": session_id
            }
        )
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "preview_id" in data
        assert "normalized_task" in data
        assert "risk" in data
        assert "lane" in data
        assert "requires_confirm" in data
        assert "ttl_seconds" in data

        # Verify normalized_task structure
        task = data["normalized_task"]
        assert "task_id" in task
        assert "author" in task
        assert "intent" in task
        assert "operations" in task

    def test_preview_low_risk_lane(self, client, session_id):
        """Test low-risk input routes to fast lane."""
        response = client.post(
            "/api/v1/chat/preview",
            json={
                "raw_input": "check status",
                "channel": "terminal",
                "session_id": session_id
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["risk"] == "low"
        assert data["lane"] == "fast"

    def test_preview_high_risk_lane(self, client, session_id):
        """Test high-risk input routes to approval lane."""
        response = client.post(
            "/api/v1/chat/preview",
            json={
                "raw_input": "lisa run deploy production",
                "channel": "terminal",
                "session_id": session_id
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["risk"] == "high"
        assert data["lane"] == "approval"

    def test_preview_requires_session_id(self, client):
        """Test /preview validates session_id."""
        response = client.post(
            "/api/v1/chat/preview",
            json={
                "raw_input": "check status",
                "channel": "terminal",
                "session_id": "invalid"  # Too short
            }
        )
        assert response.status_code == 422  # Validation error

    def test_confirm_requires_valid_preview(self, client, session_id):
        """Test /confirm rejects invalid preview_id."""
        response = client.post(
            "/api/v1/chat/confirm",
            json={
                "preview_id": str(uuid.uuid4()),  # Non-existent
                "session_id": session_id
            }
        )
        assert response.status_code == 400
        assert "PREVIEW_EXPIRED" in response.json()["detail"]

    def test_stats_returns_structure(self, client):
        """Test /stats returns session statistics."""
        response = client.get("/api/v1/chat/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_sessions" in data
        assert "total_previews" in data


class TestStatusEndpoint:
    """Test system status endpoint."""

    def test_status_returns_structure(self, client):
        """Test /status returns correct structure."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()

        assert "health" in data
        assert "staleness" in data
        assert "agents" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
