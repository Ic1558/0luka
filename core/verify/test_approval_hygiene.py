from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import approval_state, autonomy_policy


def _write_approval_state(runtime_root: Path, payload: dict) -> None:
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "approval_state.json").write_text(json.dumps(payload), encoding="utf-8")


def test_missing_approval_state_fails_closed(tmp_path) -> None:
    payload = approval_state.load_approval_state(runtime_root=tmp_path)

    assert payload["exists"] is False
    assert payload["lanes"]["memory_recovery"]["approved_effective"] is False


def test_valid_future_expiry_keeps_approval_present(tmp_path) -> None:
    _write_approval_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-08T05:00:00Z",
                "expires_at": "2099-03-08T05:10:00Z",
            }
        },
    )

    payload = approval_state.load_approval_state(runtime_root=tmp_path)

    assert payload["lanes"]["memory_recovery"]["approval_present"] is True
    assert payload["lanes"]["memory_recovery"]["approved_effective"] is True


def test_expired_approval_yields_approval_expired(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (True, "worker_ready"),
            "api_recovery": (True, "api_ready"),
            "redis_recovery": (False, "no_safe_restart_path_configured"),
        },
    )
    _write_approval_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-06T05:00:00Z",
                "expires_at": "2026-03-07T05:10:00Z",
            }
        },
    )

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path, lane="memory_recovery")

    assert payload["lanes"]["memory_recovery"]["reason"] == "approval_expired"
    assert payload["lanes"]["memory_recovery"]["approval"]["expired"] is True


def test_expiring_soon_flag_set(tmp_path) -> None:
    _write_approval_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-08T05:00:00Z",
                "expires_at": "2026-03-08T05:52:00Z",
            }
        },
    )

    payload = approval_state.load_approval_state(
        runtime_root=tmp_path,
        now=datetime(2026, 3, 8, 5, 45, 0, tzinfo=timezone.utc),
    )

    assert payload["lanes"]["memory_recovery"]["expiring_soon"] is True
    assert payload["lanes"]["memory_recovery"]["expired"] is False


def test_malformed_timestamp_fails_closed_for_lane(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (True, "worker_ready"),
            "api_recovery": (True, "api_ready"),
            "redis_recovery": (False, "no_safe_restart_path_configured"),
        },
    )
    _write_approval_state(tmp_path, {"memory_recovery": {"approved": True, "approved_by": "Boss", "approved_at": "2026-03-08T05:00:00Z", "expires_at": "bad-ts"}})

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path, lane="memory_recovery")

    assert payload["lanes"]["memory_recovery"]["status"] == "denied"
    assert payload["lanes"]["memory_recovery"]["reason"] == "approval_state_invalid"


def test_unspecified_lane_remains_fail_closed(tmp_path) -> None:
    _write_approval_state(
        tmp_path,
        {
            "worker_recovery": {
                "approved": True,
                "approved_by": "Boss",
                "approved_at": "2026-03-08T05:00:00Z",
                "expires_at": None,
            }
        },
    )

    payload = approval_state.load_approval_state(runtime_root=tmp_path)

    assert payload["lanes"]["memory_recovery"]["approved"] is False
    assert payload["lanes"]["memory_recovery"]["approved_effective"] is False


def test_mission_control_api_returns_expiry_fields(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_autonomy_policy",
        lambda lane=None: {
            "ok": True,
            "lanes": {
                "memory_recovery": {
                    "status": "approval_required",
                    "reason": "approval_expired",
                    "approval_state": "expired",
                    "expires_at": "2026-03-08T05:10:00Z",
                    "expired": True,
                    "expiring_soon": False,
                    "approval": {
                        "present": True,
                        "effective": False,
                        "expired": True,
                        "expiring_soon": False,
                        "expires_at": "2026-03-08T05:10:00Z",
                    },
                }
            },
            "errors": [],
        },
    )

    response = client.get("/api/autonomy_policy")

    assert response.status_code == 200
    lane = response.json()["lanes"]["memory_recovery"]
    assert lane["expired"] is True
    assert lane["approval"]["expired"] is True
