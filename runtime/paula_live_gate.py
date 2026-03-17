"""AG-P16: Paula Live Eligibility Gate — fail-closed, read-only."""
from __future__ import annotations
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_CLOSED_TRADES = 10
MIN_WIN_RATE = 0.40
MIN_AVG_RR = 1.0
MAX_LOSING_STREAK = 4      # block if last N closed trades are all losses


# ── Path helpers ────────────────────────────────────────────────────────────
def _runtime_root() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    return Path(rt)


def _state_dir() -> Path:
    d = _runtime_root() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    d = _runtime_root() / "artifacts" / "paula"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _atomic_append(path: Path, data: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")


# ── Signal readers (fail-closed: missing = False) ────────────────────────────
def _read_performance() -> dict | None:
    p = _state_dir() / "paula_performance_latest.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _read_paper_log() -> list[dict]:
    """Return closed trades in order from paula_paper_log.jsonl."""
    p = _state_dir() / "paula_paper_log.jsonl"
    trades: list[dict] = []
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("status") in {"closed_tp", "closed_sl", "closed_manual", "expired"}:
                    trades.append(d)
            except Exception:
                pass
    except Exception:
        pass
    return trades


def _read_approval() -> bool:
    """Check approval_state.json for paula_live_execution approval."""
    p = _state_dir() / "approval_state.json"
    try:
        state = json.loads(p.read_text())
        entry = state.get("paula_live_execution", {})
        return bool(entry.get("approved", False))
    except Exception:
        return False


def _read_watchdog() -> bool:
    """True only if supervised_heartbeat has beat > 0."""
    p = _state_dir() / "supervised_heartbeat.json"
    try:
        hb = json.loads(p.read_text())
        return int(hb.get("beat", 0)) > 0
    except Exception:
        return False


def _live_flag_enabled() -> bool:
    return os.environ.get("ENABLE_LIVE_EXECUTION", "").lower() in {"1", "true", "yes"}


# ── Gate checks ───────────────────────────────────────────────────────────────
def _check_min_closed(perf: dict | None) -> tuple[bool, str]:
    if perf is None:
        return False, "performance_metrics_unavailable"
    n = perf.get("closed_trades", 0)
    if n < MIN_CLOSED_TRADES:
        return False, f"closed_trades={n} < required {MIN_CLOSED_TRADES}"
    return True, f"closed_trades={n}"


def _check_win_rate(perf: dict | None) -> tuple[bool, str]:
    if perf is None:
        return False, "performance_metrics_unavailable"
    wr = perf.get("win_rate")
    if wr is None:
        return False, "win_rate=null (no closed trades)"
    if wr < MIN_WIN_RATE:
        return False, f"win_rate={wr} < required {MIN_WIN_RATE}"
    return True, f"win_rate={wr}"


def _check_avg_rr(perf: dict | None) -> tuple[bool, str]:
    if perf is None:
        return False, "performance_metrics_unavailable"
    rr = perf.get("avg_rr")
    if rr is None:
        return False, "avg_rr=null (no R:R data available — entry_hint missing)"
    if rr < MIN_AVG_RR:
        return False, f"avg_rr={rr} < required {MIN_AVG_RR}"
    return True, f"avg_rr={rr}"


def _check_losing_streak(closed_trades: list[dict]) -> tuple[bool, str]:
    """Block if the most recent MAX_LOSING_STREAK closed trades are all losses."""
    if not closed_trades:
        return True, "no_closed_trades"  # can't be a streak if nothing closed
    recent = closed_trades[-MAX_LOSING_STREAK:]
    all_losses = all(
        (t.get("pnl") or {}).get("result") == "loss"
        for t in recent
    )
    if len(recent) == MAX_LOSING_STREAK and all_losses:
        return False, f"losing_streak >= {MAX_LOSING_STREAK}"
    return True, f"no_{MAX_LOSING_STREAK}-trade_losing_streak"


def _check_approval(approved: bool) -> tuple[bool, str]:
    if not approved:
        return False, "paula_live_execution approval not set in approval_state.json"
    return True, "approved"


def _check_live_flag(enabled: bool) -> tuple[bool, str]:
    if not enabled:
        return False, "ENABLE_LIVE_EXECUTION env var not set or false"
    return True, "ENABLE_LIVE_EXECUTION=true"


def _check_watchdog(healthy: bool) -> tuple[bool, str]:
    if not healthy:
        return False, "supervised_heartbeat.beat=0 or unavailable"
    return True, "watchdog_active"


# ── Reason resolver ───────────────────────────────────────────────────────────
def _resolve_reason(checks: dict) -> str:
    if checks["min_closed_trades"]["pass"] is False:
        return "insufficient_data"
    if checks["win_rate_ok"]["pass"] is False:
        return "win_rate_below_threshold"
    if checks["avg_rr_ok"]["pass"] is False:
        return "avg_rr_unavailable_or_below_threshold"
    if checks["no_losing_streak"]["pass"] is False:
        return "recent_losing_streak"
    if checks["approval_active"]["pass"] is False:
        return "operator_approval_required"
    if checks["live_flag_enabled"]["pass"] is False:
        return "live_flag_not_set"
    if checks["watchdog_healthy"]["pass"] is False:
        return "watchdog_not_active"
    return "thresholds_passed"


# ── Main entry ────────────────────────────────────────────────────────────────
def run_paula_live_gate(operator_id: str = "boss") -> dict:
    """Evaluate Paula's eligibility to progress toward live execution.

    Returns eligibility record with all check results.
    Fail-closed: missing metrics always fail.
    Does NOT modify repos/, option, or any execution state.
    """
    ts = _now()
    hex8 = secrets.token_hex(4)
    trace_id = f"trace_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    eligibility_id = f"paula_live_gate_{hex8}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    perf = _read_performance()
    closed_log = _read_paper_log()
    approval = _read_approval()
    watchdog = _read_watchdog()
    live_flag = _live_flag_enabled()

    # Run all checks
    min_ok, min_detail = _check_min_closed(perf)
    wr_ok, wr_detail = _check_win_rate(perf)
    rr_ok, rr_detail = _check_avg_rr(perf)
    streak_ok, streak_detail = _check_losing_streak(closed_log)
    approval_ok, approval_detail = _check_approval(approval)
    flag_ok, flag_detail = _check_live_flag(live_flag)
    watchdog_ok, watchdog_detail = _check_watchdog(watchdog)

    checks = {
        "min_closed_trades":  {"pass": min_ok,       "detail": min_detail},
        "win_rate_ok":        {"pass": wr_ok,         "detail": wr_detail},
        "avg_rr_ok":          {"pass": rr_ok,         "detail": rr_detail},
        "no_losing_streak":   {"pass": streak_ok,     "detail": streak_detail},
        "approval_active":    {"pass": approval_ok,   "detail": approval_detail},
        "live_flag_enabled":  {"pass": flag_ok,       "detail": flag_detail},
        "watchdog_healthy":   {"pass": watchdog_ok,   "detail": watchdog_detail},
    }

    live_eligible = all(c["pass"] for c in checks.values())
    reason = _resolve_reason(checks)

    record = {
        "eligibility_id": eligibility_id,
        "operator_id": operator_id,
        "ts": ts,
        "governed": True,
        "live_eligible": live_eligible,
        "reason": reason,
        "checks": checks,
        "thresholds": {
            "min_closed_trades": MIN_CLOSED_TRADES,
            "min_win_rate": MIN_WIN_RATE,
            "min_avg_rr": MIN_AVG_RR,
            "max_losing_streak": MAX_LOSING_STREAK,
        },
    }

    # Persist
    _atomic_write(_state_dir() / "paula_live_eligibility_latest.json", record)
    _atomic_append(_state_dir() / "paula_live_eligibility_log.jsonl", record)
    _atomic_write(_artifacts_dir() / f"live_gate_{trace_id}.json", record)

    return record
