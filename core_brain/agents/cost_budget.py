from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_REGISTRY_REL = Path("core_brain/agents/model_registry.yaml")
SPEND_LEDGER_REL = Path("observability/reports/cost_router/spend_ledger.jsonl")


def _resolve_path(env_key: str, default_rel: Path) -> Path:
    raw = os.environ.get(env_key, "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else (REPO_ROOT / p)
    return REPO_ROOT / default_rel


def _load_model_registry() -> Dict[str, Any]:
    path = _resolve_path("COST_ROUTER_MODEL_REGISTRY_PATH", MODEL_REGISTRY_REL)
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("tiers"), dict):
        raise ValueError("invalid_model_registry")
    return payload


def _read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_ledger_jsonl_line:{idx}") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _entry_day(entry: Dict[str, Any]) -> str:
    ts = str(entry.get("ts_utc", ""))
    return ts[:10] if len(ts) >= 10 else ""


def check_budget(tier: str) -> Dict[str, Any]:
    registry = _load_model_registry()
    tiers = registry["tiers"]
    cfg = tiers.get(tier)
    if not isinstance(cfg, dict):
        return {"allowed": False, "reason": "invalid_tier"}

    ledger_path = _resolve_path("COST_ROUTER_SPEND_LEDGER_PATH", SPEND_LEDGER_REL)
    try:
        entries = _read_ledger(ledger_path)
    except Exception:
        return {"allowed": False, "reason": "ledger_read_failure"}

    today = _today_utc()
    daily_limit = float(cfg.get("daily_budget_limit", 0.0))
    unit_cost = float(cfg.get("unit_cost", 0.0))

    today_spend = 0.0
    t0_calls_today = 0
    for entry in entries:
        if _entry_day(entry) != today:
            continue
        amount = entry.get("amount", 0.0)
        try:
            today_spend += float(amount)
        except (TypeError, ValueError):
            continue
        if str(entry.get("tier", "")) == "T0":
            t0_calls_today += 1

    if tier == "T0":
        max_calls = cfg.get("max_daily_calls")
        if isinstance(max_calls, (int, float)) and t0_calls_today >= int(max_calls):
            return {"allowed": False, "reason": "t0_daily_limit"}

    projected = today_spend + unit_cost
    if projected > daily_limit:
        return {"allowed": False, "reason": "daily_budget_exceeded"}

    return {"allowed": True, "remaining": round(daily_limit - projected, 6)}


def record_spend(tier: str, amount: float) -> Dict[str, Any]:
    value = float(amount)
    if value < 0:
        raise ValueError("amount_must_be_non_negative")

    ledger_path = _resolve_path("COST_ROUTER_SPEND_LEDGER_PATH", SPEND_LEDGER_REL)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    payload = {
        "ts_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ts_epoch_ms": int(ts.timestamp() * 1000),
        "tier": str(tier),
        "amount": value,
    }
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError as exc:
        raise RuntimeError(f"ledger_write_failure:{ledger_path}") from exc
    return payload
