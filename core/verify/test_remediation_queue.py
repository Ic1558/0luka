from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import remediation_queue


def test_enqueue_item(tmp_path) -> None:
    payload = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )

    assert payload["ok"] is True
    item = payload["item"]
    assert item["id"].startswith("rq_")
    assert item["state"] == "queued"
    queue_file = tmp_path / "state" / "remediation_queue.json"
    assert queue_file.exists()


def test_queue_state_transition(tmp_path) -> None:
    item = remediation_queue.enqueue_item(
        lane="worker_recovery",
        action="restart_worker",
        runtime_root=tmp_path,
    )["item"]

    running = remediation_queue.transition_item(
        item_id=item["id"],
        state="running",
        runtime_root=tmp_path,
    )
    success = remediation_queue.transition_item(
        item_id=item["id"],
        state="success",
        runtime_root=tmp_path,
    )

    assert running["item"]["state"] == "running"
    assert running["item"]["attempts"] == 1
    assert success["item"]["state"] == "success"


def test_invalid_queue_request_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(tmp_path))
    client = TestClient(mission_control_server.app)

    response = client.post(
        "/api/remediation_queue/enqueue",
        json={"lane": "bad_lane", "action": "restart_worker"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert any("invalid_lane" in err for err in payload.get("errors", []))


def test_queue_api_returns_correct_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_remediation_queue",
        lambda: {
            "ok": True,
            "items": [
                {
                    "id": "rq_000001",
                    "lane": "worker_recovery",
                    "action": "restart_worker",
                    "state": "queued",
                    "attempts": 0,
                    "created_at": "2026-03-08T08:00:00Z",
                }
            ],
            "total": 1,
            "updated_at": "2026-03-08T08:00:00Z",
        },
    )

    response = client.get("/api/remediation_queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == "rq_000001"
