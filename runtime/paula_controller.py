"""AG-P12: Paula Controller — governed read-only trading brief + paper-execution adapter."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — OPTION_REPO is read-only source; all writes go to runtime state/
# ---------------------------------------------------------------------------
OPTION_REPO = Path("/Users/icmini/0luka/repos/option")

# ---------------------------------------------------------------------------
# AG-P16.7: Strategy entry model constants (from system-context / make_decision)
# SL distances per asset in native price units.
# Formula: avg_entry = SL - sl_dist (SHORT) | SL + sl_dist (LONG)
# ---------------------------------------------------------------------------
_ASSET_SL_DIST: dict[str, float] = {
    "XAUUSD": 12.0, "GC": 12.0,
    "S50": 3.0, "S50H26": 3.0, "SET50": 3.0,
    "BTCUSD": 500.0, "BTCUSD": 500.0,
    "USTEC": 80.0, "NQ": 80.0,
}


def _compute_weighted_entry(
    signal_price: float, sl: float, direction: str, symbol: str
) -> tuple[float | None, str]:
    """Derive weighted avg_entry algebraically from the strategy SL formula.

    make_decision() sets:  SL = avg_entry − d × conf["sl"]  (d: +1 LONG, -1 SHORT)
    Inverting:  LONG  → avg_entry = SL + conf["sl"]
                SHORT → avg_entry = SL - conf["sl"]

    Returns (avg_entry, source) or (None, fallback_reason).
    """
    sym_key = symbol.upper().replace("-", "").replace(" ", "").replace("=F", "")
    sl_dist = _ASSET_SL_DIST.get(sym_key)
    if sl_dist is None or not sl or direction not in {"LONG", "SHORT"}:
        return None, "signal.price_at_decision"
    if direction == "LONG":
        avg_entry = sl + sl_dist
    else:
        avg_entry = sl - sl_dist
    return round(avg_entry, 4), "weighted_avg_entry_derived_from_sl"

SAFE_READ_PATHS: dict[str, Path] = {
    "decision_history": OPTION_REPO / "artifacts/hq_decision_history.jsonl",
    "watchdog": OPTION_REPO / "artifacts/watchdog.log",
    "backtest_summary": OPTION_REPO / "artifacts/lab/backtests/BATCH_V1_3_20260311_234841/comparison_summary.json",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "artifacts" / "paula"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: dict) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read(path: Path) -> str | None:
    """Read a file only if it is inside OPTION_REPO. Raises on path escape."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(OPTION_REPO.resolve())):
        raise ValueError(f"path_outside_repo: {resolved}")
    if not resolved.exists():
        return None
    return resolved.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 1: read raw state from repos/option (read-only, path-guarded)
# ---------------------------------------------------------------------------

def read_option_state() -> dict:
    """Read all safe source files. Never raises — errors captured per-file."""
    result: dict = {
        "decisions": [],
        "watchdog_lines": [],
        "backtest_variants": [],
        "source_files": [],
        "read_errors": {},
    }

    # decision_history.jsonl
    try:
        raw = _safe_read(SAFE_READ_PATHS["decision_history"])
        if raw:
            for line in raw.strip().splitlines():
                try:
                    result["decisions"].append(json.loads(line))
                except Exception:
                    pass
            result["source_files"].append("repos/option/artifacts/hq_decision_history.jsonl")
    except Exception as exc:
        result["read_errors"]["decision_history"] = str(exc)

    # watchdog.log
    try:
        raw = _safe_read(SAFE_READ_PATHS["watchdog"])
        if raw:
            result["watchdog_lines"] = raw.strip().splitlines()
            result["source_files"].append("repos/option/artifacts/watchdog.log")
    except Exception as exc:
        result["read_errors"]["watchdog"] = str(exc)

    # backtest_summary.json
    try:
        raw = _safe_read(SAFE_READ_PATHS["backtest_summary"])
        if raw:
            parsed = json.loads(raw)
            result["backtest_variants"] = parsed if isinstance(parsed, list) else [parsed]
            result["source_files"].append(
                "repos/option/artifacts/lab/backtests/BATCH_V1_3_20260311_234841/comparison_summary.json"
            )
    except Exception as exc:
        result["read_errors"]["backtest_summary"] = str(exc)

    return result


# ---------------------------------------------------------------------------
# Phase 2: normalize into trading summary
# ---------------------------------------------------------------------------

def summarize_option_state(raw: dict) -> dict:
    """Pure normalization — no I/O, no writes."""
    summary: dict = {
        "repo_health": {},
        "strategy_mode": {},
        "current_risk_posture": {},
        "next_action_recommendation": {},
        "open_unknowns": [],
    }

    # --- repo_health: parse last watchdog line ---
    watchdog_lines = raw.get("watchdog_lines", [])
    if watchdog_lines:
        last_line = watchdog_lines[-1]
        summary["repo_health"] = {
            "last_watchdog_line": last_line,
            "line_count": len(watchdog_lines),
            "status": "healthy" if "healthy" in last_line.lower() else "unknown",
        }
    else:
        summary["repo_health"] = {"status": "no_data"}
        summary["open_unknowns"].append("watchdog.log missing or empty")

    # --- strategy_mode: last 5 decisions ---
    decisions = raw.get("decisions", [])
    last5 = decisions[-5:] if len(decisions) >= 5 else decisions
    if last5:
        latest = last5[-1]
        summary["strategy_mode"] = {
            "last_recommendation": latest.get("recommendation"),
            "last_actionable_bias": latest.get("actionable_bias"),
            "last_global_score": latest.get("global_score"),
            "last_timestamp": latest.get("timestamp"),
            "last_symbol": (latest.get("signal") or {}).get("symbol"),
            "recent_count": len(last5),
        }
    else:
        summary["strategy_mode"] = {"status": "no_decisions"}
        summary["open_unknowns"].append("decision_history missing or empty")

    # --- current_risk_posture: levels + backtest false-BEAR count ---
    levels = {}
    if decisions:
        latest_with_levels = next(
            (d for d in reversed(decisions) if d.get("levels")), None
        )
        if latest_with_levels:
            levels = latest_with_levels.get("levels", {})

    best_variant = None
    false_bear_count = None
    variants = raw.get("backtest_variants", [])
    if variants:
        try:
            best_variant = max(variants, key=lambda v: float(v.get("expectancy", 0) or 0))
            false_bear_count = best_variant.get("false_bear_count") or best_variant.get("false_BEAR_count")
        except Exception:
            pass

    summary["current_risk_posture"] = {
        "levels": levels,
        "best_backtest_variant": best_variant.get("variant") if best_variant else None,
        "best_expectancy": best_variant.get("expectancy") if best_variant else None,
        "false_bear_count": false_bear_count,
    }
    if not levels:
        summary["open_unknowns"].append("no TP/SL levels in recent decisions")
    if not best_variant:
        summary["open_unknowns"].append("backtest_summary missing or unparseable")

    # --- next_action_recommendation: from latest decision ---
    if decisions:
        latest = decisions[-1]
        signal_price_raw = (latest.get("signal") or {}).get("price")
        signal_price = float(signal_price_raw) if signal_price_raw and float(signal_price_raw) > 0 else None
        summary["next_action_recommendation"] = {
            "recommendation": latest.get("recommendation"),
            "actionable_bias": latest.get("actionable_bias"),
            "global_score": latest.get("global_score"),
            "timestamp": latest.get("timestamp"),
            "levels": latest.get("levels", {}),
            "signal_price": signal_price,
        }
    else:
        summary["next_action_recommendation"] = {"status": "no_data"}

    return summary


# ---------------------------------------------------------------------------
# Phase 3: build governed prompt
# ---------------------------------------------------------------------------

def build_brief_prompt(summary: dict) -> str:
    mode = summary.get("strategy_mode", {})
    posture = summary.get("current_risk_posture", {})
    action = summary.get("next_action_recommendation", {})
    health = summary.get("repo_health", {})

    return (
        f"Paula trading brief for repos/option. "
        f"Repo health: {health.get('status', 'unknown')}. "
        f"Last recommendation: {action.get('recommendation')} "
        f"(bias={action.get('actionable_bias')}, score={action.get('global_score')}). "
        f"Levels: {action.get('levels')}. "
        f"Best backtest: {posture.get('best_backtest_variant')} "
        f"(expectancy={posture.get('best_expectancy')}, false_bear={posture.get('false_bear_count')}). "
        f"Produce a 3-line professional read-only trading brief. No order execution. No advice."
    )


# ---------------------------------------------------------------------------
# P12: Paper trade intent, validation, and recording
# ---------------------------------------------------------------------------

def build_paper_trade_intent(summary: dict) -> dict:
    """Extract structured paper trade intent from summarize_option_state() output."""
    rec = summary.get("next_action_recommendation", {})
    levels = rec.get("levels", {})

    # Direction: prefer signal.signal, fall back to recommendation prefix
    signal_block = {}
    decisions_summary = summary.get("strategy_mode", {})
    # We need the raw signal — fetch from latest decision via strategy_mode last_symbol approach,
    # but next_action_recommendation doesn't carry signal directly. Re-derive from recommendation.
    recommendation = rec.get("recommendation") or ""
    direction = "UNKNOWN"
    if recommendation.upper().startswith("LONG"):
        direction = "LONG"
    elif recommendation.upper().startswith("SHORT"):
        direction = "SHORT"

    # Collect TP levels
    tp_levels = {k: v for k, v in levels.items() if k.startswith("TP") and v is not None}

    # Entry hierarchy (P16.7): decision_levels > weighted_avg > signal.price > null
    sl_val = levels.get("SL") or levels.get("sl") or 0
    signal_price = rec.get("signal_price")
    symbol = decisions_summary.get("last_symbol") or ""

    entry_hint: float | None = None
    entry_source: str | None = None

    if levels.get("entry") or levels.get("Entry"):
        # Tier 1: explicit entry in decision levels
        entry_hint = levels.get("entry") or levels.get("Entry")
        entry_source = "decision_levels"
    elif signal_price and sl_val and direction in {"LONG", "SHORT"} and symbol:
        # Tier 2: weighted avg_entry derived algebraically from SL formula
        weighted, w_source = _compute_weighted_entry(signal_price, sl_val, direction, symbol)
        if weighted is not None:
            entry_hint = weighted
            entry_source = w_source
        else:
            # Tier 3: raw signal.price_at_decision
            entry_hint = signal_price
            entry_source = "signal.price_at_decision"
    elif signal_price:
        # Tier 3 fallback (no SL available)
        entry_hint = signal_price
        entry_source = "signal.price_at_decision"

    entry_hint_reason = None if entry_hint else "entry_not_in_decision_levels_only_tp_sl_available"

    return {
        "symbol": decisions_summary.get("last_symbol") or "",
        "direction": direction,
        "entry_hint": entry_hint,
        "entry_hint_reason": entry_hint_reason,
        "entry_source": entry_source,
        "tp_levels": tp_levels,
        "sl": levels.get("SL") or levels.get("sl") or 0,
        "confidence": rec.get("actionable_bias") or "",
        "recommendation": recommendation,
        "global_score": rec.get("global_score") or 0,
        "status": "proposed",
        "mode": "paper",
        "executed": False,
    }


# ---------------------------------------------------------------------------
# AG-P16.8: Strategy-governed pre-trade filter
# ---------------------------------------------------------------------------
MIN_RR_FOR_TRADE = 1.0  # At least one TP must yield RR >= this to allow execution


def _compute_rr_summary(intent: dict) -> dict[str, float]:
    """Compute expected RR for every TP level using weighted entry and SL."""
    entry = intent.get("entry_hint")
    sl = intent.get("sl")
    direction = intent.get("direction")
    tp_levels = intent.get("tp_levels") or {}
    if not entry or not sl or not direction or abs(entry - sl) < 1e-9:
        return {}
    risk = abs(entry - sl)
    rr_map: dict[str, float] = {}
    for tp_name, tp_val in tp_levels.items():
        if tp_val is None:
            continue
        if direction == "LONG":
            rr = round((tp_val - entry) / risk, 3)
        else:
            rr = round((entry - tp_val) / risk, 3)
        rr_map[tp_name] = rr
    return rr_map


def apply_strategy_filter(
    intent: dict, summary: dict
) -> tuple[bool, str, dict[str, float]]:
    """Strategy-governed pre-trade filter. Fail-closed.

    Checks:
      1. actionable_bias present → else missing_required_fields
      2. global_score != 0        → else weak_signal_filtered
      3. max(TP RR) >= MIN_RR     → else rr_below_threshold

    Returns: (allowed, reason, rr_summary)
    """
    rec = summary.get("next_action_recommendation", {})
    actionable_bias = rec.get("actionable_bias") or intent.get("confidence")
    if not actionable_bias:
        return False, "missing_required_fields", {}

    global_score = rec.get("global_score")
    if global_score is None:
        return False, "missing_required_fields", {}
    if global_score == 0:
        return False, "weak_signal_filtered", {}

    rr_summary = _compute_rr_summary(intent)
    if not rr_summary:
        return False, "rr_below_threshold", rr_summary
    max_rr = max(rr_summary.values())
    if max_rr < MIN_RR_FOR_TRADE:
        return False, "rr_below_threshold", rr_summary

    return True, "passed", rr_summary


def validate_paper_trade(intent: dict) -> tuple[bool, str]:
    """Risk gate — fail-closed on hard checks; soft checks append to warnings only."""
    # Hard checks
    if not intent.get("symbol"):
        return False, "block_reason: symbol_missing"
    if intent.get("direction") not in {"LONG", "SHORT"}:
        return False, f"block_reason: direction_invalid={intent.get('direction')}"
    if not intent.get("sl"):
        return False, "block_reason: sl_missing_or_zero"
    if not intent.get("tp_levels"):
        return False, "block_reason: no_tp_levels"
    if not intent.get("recommendation"):
        return False, "block_reason: recommendation_empty"
    return True, "ok"


def record_paper_trade(intent: dict, brief_id: str, operator_id: str) -> dict:
    """Write paper trade record atomically to state/ and artifacts/paula/."""
    ts = _now()
    uid8 = uuid.uuid4().hex[:8]
    paper_trade_id = f"paula_paper_{uid8}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    paper_record: dict = {
        "paper_trade_id": paper_trade_id,
        "brief_id": brief_id,
        "operator_id": operator_id,
        "symbol": intent.get("symbol"),
        "direction": intent.get("direction"),
        "entry_hint": intent.get("entry_hint"),
        "tp_levels": intent.get("tp_levels", {}),
        "sl": intent.get("sl"),
        "confidence": intent.get("confidence"),
        "recommendation": intent.get("recommendation"),
        "global_score": intent.get("global_score"),
        "mode": "paper",
        "executed": False,
        "governed": True,
        "status": "recorded",
        "ts": ts,
        "opened_at": intent.get("ts") or ts,
        "closed_at": None,
        "close_reason": None,
        "pnl": None,
    }

    sd = _state_dir()
    _atomic_write(sd / "paula_paper_latest.json", paper_record)
    _append_jsonl(sd / "paula_paper_log.jsonl", paper_record)

    ad = _artifacts_dir()
    _atomic_write(ad / f"{paper_trade_id}.json", paper_record)

    return paper_record


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_paula_brief(operator_id: str = "boss", provider: str = "claude") -> dict:
    """Governed read-only Paula brief. Returns full evidence record."""
    from runtime.operator_task import _check_approval
    from runtime.governed_inference import route_inference

    brief_id = f"paula_{uuid.uuid4().hex[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    ts = _now()

    # --- approval gate (fail-closed) ---
    approved, approval_reason = _check_approval()
    if not approved:
        record: dict = {
            "brief_id": brief_id,
            "task_id": "paula_brief",
            "operator_id": operator_id,
            "provider": provider,
            "ts": ts,
            "governed": True,
            "approved": False,
            "block_reason": approval_reason,
            "source_files": [],
            "summary": {},
            "inference_id": None,
            "brief": None,
            "status": "blocked",
        }
        sd = _state_dir()
        _atomic_write(sd / "paula_brief_latest.json", record)
        _append_jsonl(sd / "paula_brief_log.jsonl", record)
        return record

    # --- read + summarize ---
    raw = read_option_state()
    summary = summarize_option_state(raw)
    prompt = build_brief_prompt(summary)

    # --- governed inference ---
    inference_result = route_inference(prompt, provider, operator_id)
    brief_text: str | None = inference_result.get("response")

    # --- paper trade intent + P16.8 strategy filter + validation ---
    intent = build_paper_trade_intent(summary)
    filter_allowed, filter_reason, rr_summary = apply_strategy_filter(intent, summary)

    paper_record = None
    filter_decision = "skipped" if not filter_allowed else "executed"

    if not filter_allowed:
        paper_status = f"skipped:{filter_reason}"
    else:
        paper_valid, paper_reason = validate_paper_trade(intent)
        if paper_valid:
            paper_record = record_paper_trade(intent, brief_id, operator_id)
            paper_status = "recorded"
        else:
            paper_status = f"blocked:{paper_reason}"
            filter_decision = "skipped"
            filter_reason = paper_reason

    record = {
        "brief_id": brief_id,
        "task_id": "paula_brief",
        "operator_id": operator_id,
        "provider": provider,
        "ts": ts,
        "governed": True,
        "approved": True,
        "block_reason": None,
        "source_files": raw.get("source_files", []),
        "summary": summary,
        "inference_id": inference_result.get("inference_id"),
        "brief": brief_text,
        "filter_decision": filter_decision,
        "filter_reason": filter_reason,
        "rr_summary": rr_summary,
        "paper_trade_id": paper_record["paper_trade_id"] if paper_record else None,
        "paper_trade_status": paper_status,
        "paper_trade": paper_record,
        "status": "executed",
    }

    # --- write evidence ---
    sd = _state_dir()
    _atomic_write(sd / "paula_brief_latest.json", record)
    _append_jsonl(sd / "paula_brief_log.jsonl", record)

    ad = _artifacts_dir()
    _atomic_write(ad / f"{brief_id}.json", record)

    return record
