from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import approval_presets, autonomy_policy


def test_list_presets_works(tmp_path) -> None:
    payload = approval_presets.list_presets(runtime_root=tmp_path)
    names = [row["name"] for row in payload["presets"]]
    assert payload["ok"] is True
    assert names == ["memory_only", "worker_only", "safe_local_ops", "manual_only"]


def test_apply_preset_writes_correct_events(tmp_path) -> None:
    payload = approval_presets.apply_preset(preset="safe_local_ops", runtime_root=tmp_path)
    actions = [entry["action"] for result in payload["results"] for entry in result["audit_entries"]]
    actors = [entry["actor"] for result in payload["results"] for entry in result["audit_entries"]]

    assert payload["ok"] is True
    assert payload["lanes"] == ["memory_recovery", "worker_recovery"]
    assert actions == ["approve", "approve"]
    assert all(actor == "preset:safe_local_ops" for actor in actors)


def test_reset_preset_writes_revoke_events(tmp_path) -> None:
    approval_presets.apply_preset(preset="safe_local_ops", runtime_root=tmp_path)
    payload = approval_presets.reset_preset(preset="safe_local_ops", runtime_root=tmp_path)
    actions = [entry["action"] for result in payload["results"] for entry in result["audit_entries"]]

    assert payload["ok"] is True
    assert actions == ["revoke", "revoke"]


def test_autonomy_policy_reflects_preset_effect(tmp_path, monkeypatch) -> None:
    approval_presets.apply_preset(preset="memory_only", runtime_root=tmp_path)
    monkeypatch.setenv("LUKA_ALLOW_MEMORY_RECOVERY", "1")
    monkeypatch.setattr(
        autonomy_policy,
        "_lane_availability",
        lambda runtime_root: {
            "memory_recovery": (True, "available"),
            "worker_recovery": (True, "available"),
            "api_recovery": (True, "available"),
            "redis_recovery": (False, "no_safe_restart_path_configured"),
        },
    )

    payload = autonomy_policy.evaluate_policy(runtime_root=tmp_path, lane="memory_recovery")

    assert payload["lanes"]["memory_recovery"]["approval_state"] == "present"
    assert payload["lanes"]["memory_recovery"]["status"] == "allowed"


def test_invalid_preset_rejected(tmp_path) -> None:
    try:
        approval_presets.apply_preset(preset="bad_preset", runtime_root=tmp_path)
    except RuntimeError as exc:
        assert "unknown_preset" in str(exc)
    else:
        raise AssertionError("invalid preset should fail")


def test_approval_history_api_includes_preset_events(tmp_path, monkeypatch) -> None:
    approval_presets.apply_preset(preset="memory_only", runtime_root=tmp_path)
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(tmp_path))
    client = TestClient(mission_control_server.app)

    response = client.get("/api/approval_history")
    payload = response.json()

    assert response.status_code == 200
    assert payload["events"]
    assert payload["events"][-1]["actor"] == "preset:memory_only"
