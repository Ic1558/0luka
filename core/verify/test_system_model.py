from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import system_model


def test_build_system_model_returns_expected_keys() -> None:
    payload = system_model.build_system_model()

    assert set(payload) == {
        "schema_version",
        "ts_utc",
        "current_phase",
        "system_classification",
        "eligibility_to_act",
        "eligibility_reason",
        "repos_qs_boundary",
        "control_plane_enabled",
        "autonomy_enabled",
        "decision_memory_present",
    }


def test_eligibility_to_act_is_false() -> None:
    payload = system_model.build_system_model()

    assert payload["eligibility_to_act"] is False
    assert payload["eligibility_reason"] == "control-plane not implemented"


def test_repos_qs_boundary_is_frozen_canonical() -> None:
    payload = system_model.build_system_model()

    assert payload["repos_qs_boundary"] == "frozen_canonical"
    assert payload["control_plane_enabled"] is False
    assert payload["autonomy_enabled"] is False


def test_write_system_model_writes_atomically(tmp_path: Path) -> None:
    target = tmp_path / "state" / "system_model.json"

    system_model.write_system_model(target)

    assert target.exists()
    assert not (tmp_path / "state" / "system_model.json.tmp").exists()


def test_file_lands_under_runtime_root_state_system_model_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(tmp_path))

    exit_code = system_model.main()
    target = tmp_path / "state" / "system_model.json"

    assert exit_code == 0
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8"))["current_phase"] == "I"


def test_no_forbidden_dynamic_action_fields_are_present(tmp_path: Path) -> None:
    target = tmp_path / "state" / "system_model.json"

    system_model.write_system_model(target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert "action" not in payload
    assert "remediation" not in payload
    assert "queue" not in payload
    assert "mutation" not in payload
