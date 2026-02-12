from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core_brain.agents.cost_budget import check_budget, record_spend


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mk_registry() -> dict:
    return {
        "tiers": {
            "T0": {"name": "t0", "models": ["m0"], "daily_budget_limit": 100.0, "unit_cost": 5.0, "max_daily_calls": 1},
            "T1": {"name": "t1", "models": ["m1"], "daily_budget_limit": 20.0, "unit_cost": 2.0},
            "T2": {"name": "t2", "models": ["m2"], "daily_budget_limit": 10.0, "unit_cost": 1.0},
            "T3": {"name": "t3", "models": ["m3"], "daily_budget_limit": 5.0, "unit_cost": 0.5},
            "T4": {"name": "t4", "models": ["m4"], "daily_budget_limit": 2.0, "unit_cost": 0.1},
        }
    }


def _setup_env(tmp_path: Path, monkeypatch) -> Path:
    registry_path = tmp_path / "model_registry.yaml"
    ledger_path = tmp_path / "spend_ledger.jsonl"
    _write_json(registry_path, _mk_registry())
    monkeypatch.setenv("COST_ROUTER_MODEL_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("COST_ROUTER_SPEND_LEDGER_PATH", str(ledger_path))
    return ledger_path


def test_budget_allow_within_limit(tmp_path: Path, monkeypatch) -> None:
    ledger = _setup_env(tmp_path, monkeypatch)
    ledger.write_text(json.dumps({"ts_utc": _today_iso(), "tier": "T2", "amount": 2.0}) + "\n", encoding="utf-8")
    out = check_budget("T2")
    assert out["allowed"] is True
    assert "remaining" in out


def test_budget_deny_daily_limit(tmp_path: Path, monkeypatch) -> None:
    ledger = _setup_env(tmp_path, monkeypatch)
    # T2 limit = 10.0, unit cost = 1.0, existing spend = 10.0 => deny projected > 10.0
    ledger.write_text(json.dumps({"ts_utc": _today_iso(), "tier": "T2", "amount": 10.0}) + "\n", encoding="utf-8")
    out = check_budget("T2")
    assert out == {"allowed": False, "reason": "daily_budget_exceeded"}


def test_budget_deny_ledger_failure(tmp_path: Path, monkeypatch) -> None:
    ledger = _setup_env(tmp_path, monkeypatch)
    ledger.write_text("{not-json}\n", encoding="utf-8")
    out = check_budget("T2")
    assert out == {"allowed": False, "reason": "ledger_read_failure"}


def test_budget_deny_t0_daily_limit(tmp_path: Path, monkeypatch) -> None:
    ledger = _setup_env(tmp_path, monkeypatch)
    ledger.write_text(json.dumps({"ts_utc": _today_iso(), "tier": "T0", "amount": 5.0}) + "\n", encoding="utf-8")
    out = check_budget("T0")
    assert out == {"allowed": False, "reason": "t0_daily_limit"}


def test_record_spend_writes_valid_jsonl(tmp_path: Path, monkeypatch) -> None:
    ledger = _setup_env(tmp_path, monkeypatch)
    record = record_spend("T1", 1.25)
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["tier"] == "T1"
    assert float(parsed["amount"]) == 1.25
    assert parsed["ts_utc"]
    assert parsed["ts_epoch_ms"] >= 0
    assert record["tier"] == "T1"


def test_agent_config_file_is_parseable_json_yaml() -> None:
    cfg = Path("core_brain/agents/agent_config.yaml")
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert "agents" in payload
