from __future__ import annotations

import json
from pathlib import Path

from core_brain.agents.cost_router import (
    classify_complexity,
    classify_risk,
    has_governance_impact,
    select_model,
)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mk_registry() -> dict:
    return {
        "tiers": {
            "T0": {"name": "t0", "models": ["m0"], "daily_budget_limit": 100.0, "unit_cost": 5.0, "max_daily_calls": 2},
            "T1": {"name": "t1", "models": ["m1"], "daily_budget_limit": 50.0, "unit_cost": 2.0},
            "T2": {"name": "t2", "models": ["m2"], "daily_budget_limit": 20.0, "unit_cost": 1.0},
            "T3": {"name": "t3", "models": ["m3"], "daily_budget_limit": 10.0, "unit_cost": 0.5},
            "T4": {"name": "t4", "models": ["m4"], "daily_budget_limit": 5.0, "unit_cost": 0.1},
        }
    }


def _setup_env(tmp_path: Path, monkeypatch) -> Path:
    registry_path = tmp_path / "model_registry.yaml"
    decisions_path = tmp_path / "decisions.jsonl"
    _write_json(registry_path, _mk_registry())
    monkeypatch.setenv("COST_ROUTER_MODEL_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("COST_ROUTER_DECISIONS_PATH", str(decisions_path))
    return decisions_path


def test_r3_path_routes_to_t0(tmp_path: Path, monkeypatch) -> None:
    decisions = _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t1", "path": "core/config.py", "intent": "typo"}
    out = select_model(task)
    assert classify_risk(task) == "R3"
    assert out["tier_selected"] == "T0"
    assert decisions.exists()


def test_r0_path_routes_to_t3(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t2", "path": "observability/logs/x.json", "intent": "typo"}
    out = select_model(task)
    assert classify_risk(task) == "R0"
    assert classify_complexity(task) == "L0"
    assert out["tier_selected"] == "T3"


def test_l3_intent_routes_to_t0(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t3", "path": "docs/readme.md", "intent": "refactor architecture"}
    out = select_model(task)
    assert classify_complexity(task) == "L3_plus"
    assert out["tier_selected"] == "T0"


def test_governance_override_routes_to_t0(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t4", "intent": "modifies:core/governance/phase_status.yaml typo"}
    assert has_governance_impact(task) is True
    out = select_model(task)
    assert out["tier_selected"] == "T0"


def test_composition_higher_floor_wins(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    # R1 => T2, L2 => T1, stricter floor is T1.
    task = {"task_id": "t5", "path": "modules/example/file.py", "intent": "implement feature"}
    out = select_model(task)
    assert classify_risk(task) == "R1"
    assert classify_complexity(task) == "L2"
    assert out["tier_selected"] == "T1"


def test_determinism_replay_100(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t6", "path": "modules/example/file.py", "intent": "bug fix"}
    tiers = [select_model(task)["tier_selected"] for _ in range(100)]
    assert len(set(tiers)) == 1


def test_decision_log_line_per_call(tmp_path: Path, monkeypatch) -> None:
    decisions = _setup_env(tmp_path, monkeypatch)
    task = {"task_id": "t7", "path": "modules/example/file.py", "intent": "feature"}
    select_model(task)
    lines = decisions.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["task_id"] == "t7"
    assert payload["tier_selected"] in {"T0", "T1", "T2", "T3", "T4"}


def test_model_registry_file_is_parseable_json_yaml() -> None:
    registry = Path("core_brain/agents/model_registry.yaml")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    assert "tiers" in payload
