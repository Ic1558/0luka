from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import autonomy_policy


def _write_approval_state(runtime_root: Path, payload: dict) -> None:
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "approval_state.json").write_text(json.dumps(payload), encoding="utf-8")


def test_missing_approval_state_fails_closed(monkeypatch, tmp_path) -> None:
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

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path)

    assert payload["lanes"]["memory_recovery"]["status"] == "approval_required"
    assert payload["lanes"]["worker_recovery"]["status"] == "approval_required"
    assert payload["lanes"]["redis_recovery"]["status"] == "unavailable"


def test_valid_approval_state_allows_approved_lane(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LUKA_ALLOW_MEMORY_RECOVERY", "1")
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (False, "worker_unavailable"),
            "api_recovery": (False, "api_unavailable"),
            "redis_recovery": (False, "redis_unavailable"),
        },
    )
    _write_approval_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "operator",
                "approved_at": "2026-03-08T08:00:00Z",
                "expires_at": "2026-03-09T08:00:00Z",
            }
        },
    )

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path)

    assert payload["lanes"]["memory_recovery"]["status"] == "allowed"
    assert payload["lanes"]["memory_recovery"]["reason"] == "approved_and_available"


def test_expired_approval_requires_approval(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LUKA_ALLOW_MEMORY_RECOVERY", "1")
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (False, "worker_unavailable"),
            "api_recovery": (False, "api_unavailable"),
            "redis_recovery": (False, "redis_unavailable"),
        },
    )
    _write_approval_state(
        tmp_path,
        {
            "memory_recovery": {
                "approved": True,
                "approved_by": "operator",
                "approved_at": "2026-03-06T08:00:00Z",
                "expires_at": "2026-03-07T08:00:00Z",
            }
        },
    )

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path)

    assert payload["lanes"]["memory_recovery"]["status"] == "approval_required"
    assert payload["lanes"]["memory_recovery"]["reason"] == "approval_expired"


def test_invalid_approval_file_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (True, "worker_ready"),
            "api_recovery": (False, "api_unavailable"),
            "redis_recovery": (False, "redis_unavailable"),
        },
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "approval_state.json").write_text('{"memory_recovery":{"approved":"yes"}}', encoding="utf-8")

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path)

    assert payload["approval_state"]["valid"] is False
    assert payload["lanes"]["memory_recovery"]["status"] == "denied"


def test_lane_filter_works(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "memory_ready"),
            "worker_recovery": (True, "worker_ready"),
            "api_recovery": (True, "api_ready"),
            "redis_recovery": (False, "redis_unavailable"),
        },
    )

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path, lane="memory_recovery")

    assert list(payload["lanes"].keys()) == ["memory_recovery"]


def test_mission_control_api_returns_valid_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_autonomy_policy",
        lambda lane=None: {
            "ok": True,
            "lanes": {
                "memory_recovery": {
                    "status": "approval_required",
                    "reason": "approval_missing",
                    "approval_state": "missing",
                    "expires_at": None,
                }
            },
            "errors": [],
        },
    )

    response = client.get("/api/autonomy_policy")

    assert response.status_code == 200
    assert response.json()["lanes"]["memory_recovery"]["status"] == "approval_required"
