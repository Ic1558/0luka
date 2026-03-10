from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import approval_state, approval_write


def _read_state(runtime_root: Path) -> dict:
    return json.loads((runtime_root / "state" / "approval_state.json").read_text(encoding="utf-8"))


def _read_audit(runtime_root: Path) -> list[dict]:
    path = runtime_root / "state" / "approval_actions.jsonl"
    if not path.exists():
        return []
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def test_approve_valid_lane(tmp_path) -> None:
    payload = approval_write.write_approval_action(
        lane="memory_recovery",
        actor="Boss",
        approve=True,
        runtime_root=tmp_path,
    )

    assert payload["ok"] is True
    state = _read_state(tmp_path)
    assert state["memory_recovery"]["approved"] is True
    assert state["memory_recovery"]["approved_by"] == "Boss"


def test_revoke_valid_lane(tmp_path) -> None:
    approval_write.write_approval_action(
        lane="worker_recovery",
        actor="Boss",
        approve=True,
        runtime_root=tmp_path,
    )

    payload = approval_write.write_approval_action(
        lane="worker_recovery",
        actor="Boss",
        revoke=True,
        runtime_root=tmp_path,
    )

    assert payload["ok"] is True
    state = _read_state(tmp_path)
    assert state["worker_recovery"]["approved"] is False
    assert state["worker_recovery"]["approved_by"] is None


def test_invalid_lane_fails(tmp_path) -> None:
    try:
        approval_write.write_approval_action(
            lane="bad_lane",
            actor="Boss",
            approve=True,
            runtime_root=tmp_path,
        )
    except RuntimeError as exc:
        assert "unsupported_lane" in str(exc)
    else:
        raise AssertionError("invalid lane should fail")


def test_expiry_validation_fails_on_bad_format(tmp_path) -> None:
    try:
        approval_write.write_approval_action(
            lane="memory_recovery",
            actor="Boss",
            approve=True,
            expires_at="bad-ts",
            runtime_root=tmp_path,
        )
    except RuntimeError as exc:
        assert "expires_at" in str(exc)
    else:
        raise AssertionError("bad expiry should fail")


def test_audit_log_entry_valid(tmp_path) -> None:
    approval_write.write_approval_action(
        lane="api_recovery",
        actor="Boss",
        approve=True,
        expires_at="2026-03-09T12:00:00Z",
        runtime_root=tmp_path,
    )

    rows = _read_audit(tmp_path)
    assert len(rows) == 2
    assert rows[0]["action"] == "approve"
    assert rows[1]["action"] == "set_expiry"
    assert rows[0]["source"] == "approval_write"


def test_mission_control_approval_endpoint_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "apply_approval_action",
        lambda **kwargs: {"ok": True, "lane": kwargs["lane"], "state": {"approved": True}},
    )

    response = client.post("/api/approval/approve", json={"lane": "memory_recovery", "actor": "Boss"})

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_unspecified_lanes_remain_fail_closed(tmp_path) -> None:
    approval_write.write_approval_action(
        lane="memory_recovery",
        actor="Boss",
        approve=True,
        runtime_root=tmp_path,
    )

    state = _read_state(tmp_path)
    for lane in approval_state.LANES:
        if lane == "memory_recovery":
            continue
        assert state[lane]["approved"] is False
