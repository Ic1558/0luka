from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bridge.ag_bridge import AgBridgeResponse  # noqa: E402
from tools.bridge.bridge_server import app  # noqa: E402
import tools.bridge.bridge_server as bridge_server  # noqa: E402


def _valid_body() -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000111",
        "source": "antigravity",
        "agent": "cole",
        "task": "cole.search_docs",
        "args": {"query": "status"},
        "created_at_utc": "2026-03-14T00:00:00Z",
    }


def _client() -> TestClient:
    bridge_server._rate_buckets.clear()
    bridge_server._schema = None
    return TestClient(app)


def test_health_returns_ok() -> None:
    client = _client()
    response = client.get("/api/bridge/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_dispatch_no_token_configured(monkeypatch) -> None:
    monkeypatch.delenv("AG_BRIDGE_TOKEN", raising=False)
    client = _client()
    response = client.post("/api/bridge/dispatch", json=_valid_body())
    assert response.status_code == 503
    assert response.json()["error"] == "bridge_token_not_configured"


def test_dispatch_wrong_token(monkeypatch) -> None:
    monkeypatch.setenv("AG_BRIDGE_TOKEN", "secret")
    client = _client()
    response = client.post(
        "/api/bridge/dispatch",
        json=_valid_body(),
        headers={"X-Bridge-Token": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_dispatch_invalid_schema(monkeypatch) -> None:
    monkeypatch.setenv("AG_BRIDGE_TOKEN", "secret")
    client = _client()
    bad = _valid_body()
    bad.pop("task")
    response = client.post(
        "/api/bridge/dispatch",
        json=bad,
        headers={"X-Bridge-Token": "secret"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "schema_invalid"


def test_dispatch_rate_limit(monkeypatch) -> None:
    monkeypatch.setenv("AG_BRIDGE_TOKEN", "secret")
    monkeypatch.setattr(
        bridge_server,
        "dispatch",
        lambda body: AgBridgeResponse(
            request_id="r1",
            status="accepted",
            task_id="t1",
            error=None,
            policy_blocked=False,
        ),
    )
    client = _client()
    headers = {"X-Bridge-Token": "secret"}
    for _ in range(30):
        response = client.post("/api/bridge/dispatch", json=_valid_body(), headers=headers)
        assert response.status_code == 202
    response = client.post("/api/bridge/dispatch", json=_valid_body(), headers=headers)
    assert response.status_code == 429
    assert response.json()["error"] == "rate_limit_exceeded"


def test_dispatch_accepted(monkeypatch) -> None:
    monkeypatch.setenv("AG_BRIDGE_TOKEN", "secret")
    monkeypatch.setattr(
        bridge_server,
        "dispatch",
        lambda body: AgBridgeResponse(
            request_id="r1",
            status="accepted",
            task_id="t1",
            error=None,
            policy_blocked=False,
        ),
    )
    client = _client()
    response = client.post(
        "/api/bridge/dispatch",
        json=_valid_body(),
        headers={"X-Bridge-Token": "secret"},
    )
    assert response.status_code == 202
    assert response.json()["task_id"] == "t1"


def test_dispatch_blocked(monkeypatch) -> None:
    monkeypatch.setenv("AG_BRIDGE_TOKEN", "secret")
    monkeypatch.setattr(
        bridge_server,
        "dispatch",
        lambda body: AgBridgeResponse(
            request_id="r2",
            status="blocked",
            task_id=None,
            error="blocked_by_policy_freeze",
            policy_blocked=True,
        ),
    )
    client = _client()
    response = client.post(
        "/api/bridge/dispatch",
        json=_valid_body(),
        headers={"X-Bridge-Token": "secret"},
    )
    assert response.status_code == 503
    assert response.json()["policy_blocked"] is True

