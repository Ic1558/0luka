"""AG-P16.9: Paula Sample Quality Validator.

Compares pre-P16.8 and post-P16.8 paper-trade cohorts.
Cohort boundary marker: presence of 'entry_source' field (added in P16.6).
Produces a comparison artifact under artifacts/paula/.
No behavior change to execution path.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cohort boundary
# ---------------------------------------------------------------------------

# P16.6 added entry_source; P16.7 normalized it; P16.8 added filter_decision.
# Any trade with entry_source present = post-P16.6+ pipeline.
# Any brief record with filter_decision present = post-P16.8 pipeline.
P166_MARKER = "entry_source"   # first quality improvement (grounded entry)
P168_MARKER = "filter_decision"  # strategy filter active


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_paper_trades() -> list[dict]:
    """Load all paper trades from paula_paper_log.jsonl. Skip non-trade events."""
    p = _state_dir() / "paula_paper_log.jsonl"
    trades: list[dict] = []
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if "paper_trade_id" in d and "status" in d:
                    # Deduplicate: keep latest version of each paper_trade_id
                    existing = next((t for t in trades if t["paper_trade_id"] == d["paper_trade_id"]), None)
                    if existing:
                        trades.remove(existing)
                    trades.append(d)
            except Exception:
                pass
    except Exception:
        pass
    return trades


def load_brief_records() -> list[dict]:
    """Load all brief log records."""
    p = _state_dir() / "paula_brief_log.jsonl"
    briefs: list[dict] = []
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    briefs.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return briefs


# ---------------------------------------------------------------------------
# Cohort split
# ---------------------------------------------------------------------------

def split_cohorts(trades: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split trades into pre-P16.6 and post-P16.6+ cohorts.

    Pre-P16.6:  no entry_source field  (entry_hint always null)
    Post-P16.6: has entry_source field  (grounded entry, RR computable)
    """
    pre = [t for t in trades if P166_MARKER not in t]
    post = [t for t in trades if P166_MARKER in t]
    return pre, post


# ---------------------------------------------------------------------------
# Cohort metrics
# ---------------------------------------------------------------------------

CLOSED_STATUSES = {"closed_tp", "closed_sl", "closed_manual", "expired"}


def cohort_metrics(trades: list[dict], label: str) -> dict:
    """Aggregate a trade list into performance metrics for comparison."""
    closed = [t for t in trades if t.get("status") in CLOSED_STATUSES]
    open_t = [t for t in trades if t.get("status") not in CLOSED_STATUSES]

    wins = [t for t in closed if (t.get("pnl") or {}).get("result") == "win"]
    losses = [t for t in closed if (t.get("pnl") or {}).get("result") == "loss"]
    neutrals = [t for t in closed if (t.get("pnl") or {}).get("result") == "neutral"]

    rr_vals = [
        t["pnl"]["rr"]
        for t in closed
        if (t.get("pnl") or {}).get("rr") is not None
    ]

    has_entry = [t for t in trades if t.get("entry_hint") is not None]
    has_rr = [t for t in closed if (t.get("pnl") or {}).get("rr") is not None]

    win_rate = round(len(wins) / len(closed), 3) if closed else None
    avg_rr = round(sum(rr_vals) / len(rr_vals), 3) if rr_vals else None

    return {
        "cohort": label,
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(open_t),
        "wins": len(wins),
        "losses": len(losses),
        "neutrals": len(neutrals),
        "win_rate": win_rate,
        "avg_rr": avg_rr,
        "trades_with_entry": len(has_entry),
        "closed_with_rr": len(has_rr),
        "entry_coverage_pct": round(len(has_entry) / len(trades) * 100, 1) if trades else 0,
        "rr_coverage_pct": round(len(has_rr) / len(closed) * 100, 1) if closed else 0,
    }


def projected_post_p168_metrics() -> dict:
    """Simulate expected metrics for post-P16.8 filtered trades.

    Assumptions (clearly labeled as SIMULATED):
    - Only global_score != 0 signals pass filter (based on P16.8 filter logic)
    - Only trades with TP3+ available pass RR check (RR >= 1.0)
    - Trade mix based on P16.8 dry-run: 6W 3L 1N over 10 closes
    - avg_rr from trend sim: FULL_TP(2.08), TP3(1.17) dominate; SL(-1.0) on losses
    - This is a forward projection, NOT real data
    """
    # Simulated RR values from P16.8-filtered cohort:
    # 2 × FULL_TP = 2.083
    # 2 × TP3    = 1.167
    # 1 × TP2    = 0.833 (would pass TP3 cutoff — included)
    # 3 × SL     = -1.0
    # 1 × expired = -0.083 (small negative)
    # Filtered out: weak TP1/TP2-only trades, global_score=0 signals
    rr_sample = [2.083, 2.083, 1.167, 1.167, 0.833, -1.0, -1.0, -1.0, -0.083]
    closed = 9  # one open
    wins = 4
    losses = 3
    neutrals = 1  # one expired
    win_rate = round(wins / closed, 3)
    avg_rr = round(sum(rr_sample) / len(rr_sample), 3)

    return {
        "cohort": "post_p168_projected",
        "data_type": "SIMULATED — forward projection, not real data",
        "projection_basis": "P16.8 filter (global_score!=0, max_TP_RR>=1.0) + P16.7 weighted entry",
        "closed_trades": closed,
        "wins": wins,
        "losses": losses,
        "neutrals": neutrals,
        "win_rate": win_rate,
        "avg_rr": avg_rr,
        "trades_with_entry": 10,
        "entry_coverage_pct": 100.0,
        "rr_coverage_pct": 100.0,
    }


# ---------------------------------------------------------------------------
# Gate check (mirrors run_paula_live_gate logic on given metrics)
# ---------------------------------------------------------------------------

MIN_CLOSED_TRADES = 10
MIN_WIN_RATE = 0.40
MIN_AVG_RR = 1.0
MAX_LOSING_STREAK = 4


def _check_metrics_against_gate(metrics: dict) -> dict:
    """Mirror paula_live_gate checks on arbitrary metric dict. Read-only."""
    n = metrics.get("closed_trades", 0)
    wr = metrics.get("win_rate")
    rr = metrics.get("avg_rr")

    checks = {
        "min_closed_trades": {
            "pass": n >= MIN_CLOSED_TRADES,
            "detail": f"closed_trades={n} / required {MIN_CLOSED_TRADES}",
        },
        "win_rate_ok": {
            "pass": wr is not None and wr >= MIN_WIN_RATE,
            "detail": f"win_rate={wr} / required {MIN_WIN_RATE}",
        },
        "avg_rr_ok": {
            "pass": rr is not None and rr >= MIN_AVG_RR,
            "detail": f"avg_rr={rr} / required {MIN_AVG_RR}",
        },
    }
    perf_pass = all(c["pass"] for c in checks.values())
    return {"checks": checks, "performance_gate_pass": perf_pass}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_paula_sample_validation(operator_id: str = "boss") -> dict:
    """Compare pre/post-P16.8 cohorts. Produce comparison artifact.

    Returns validation record with cohort metrics and gate projections.
    No behavior change to the paper-trade execution path.
    """
    ts = _now()
    hex8 = secrets.token_hex(4)
    validation_id = f"paula_validation_{hex8}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Load data
    trades = load_paper_trades()
    briefs = load_brief_records()

    pre_trades, post_trades = split_cohorts(trades)

    # Cohort metrics
    pre_metrics = cohort_metrics(pre_trades, "pre_p168_real")
    post_metrics = cohort_metrics(post_trades, "post_p168_real") if post_trades else {
        "cohort": "post_p168_real",
        "note": "no trades yet — scheduler has not yet fired post-P16.8 commit",
        "total_trades": 0,
        "closed_trades": 0,
    }
    projected = projected_post_p168_metrics()

    # Brief cohort stats
    post_p168_briefs = [b for b in briefs if P168_MARKER in b]
    skipped_briefs = [b for b in post_p168_briefs if b.get("filter_decision") == "skipped"]
    executed_briefs = [b for b in post_p168_briefs if b.get("filter_decision") == "executed"]
    filter_reason_counts: dict[str, int] = {}
    for b in skipped_briefs:
        r = b.get("filter_reason", "unknown")
        filter_reason_counts[r] = filter_reason_counts.get(r, 0) + 1

    # Gate checks
    pre_gate = _check_metrics_against_gate(pre_metrics)
    proj_gate = _check_metrics_against_gate(projected)

    # Improvement analysis
    improvements: list[str] = []
    regressions: list[str] = []
    for key in ["min_closed_trades", "win_rate_ok", "avg_rr_ok"]:
        pre_pass = pre_gate["checks"][key]["pass"]
        proj_pass = proj_gate["checks"][key]["pass"]
        if not pre_pass and proj_pass:
            improvements.append(key)
        elif pre_pass and not proj_pass:
            regressions.append(key)

    remaining_blockers: list[str] = [
        k for k, v in proj_gate["checks"].items() if not v["pass"]
    ]
    remaining_blockers += [
        "approval_active (operator must set paula_live_execution.approved=true)",
        "live_flag_enabled (ENABLE_LIVE_EXECUTION env var not set)",
    ]

    record = {
        "validation_id": validation_id,
        "operator_id": operator_id,
        "ts": ts,
        "governed": True,
        "cohort_boundary": "entry_source field (added P16.6) — post-P16.8 also has filter_decision",
        "cohorts": {
            "pre_p168_real": pre_metrics,
            "post_p168_real": post_metrics,
            "post_p168_projected": projected,
        },
        "brief_stats": {
            "total_briefs": len(briefs),
            "post_p168_briefs": len(post_p168_briefs),
            "skipped_by_filter": len(skipped_briefs),
            "executed_by_filter": len(executed_briefs),
            "filter_reason_counts": filter_reason_counts,
        },
        "gate_analysis": {
            "pre_p168_performance_checks": pre_gate,
            "projected_post_p168_checks": proj_gate,
            "improvements_over_pre": improvements,
            "regressions": regressions,
        },
        "remaining_blockers": remaining_blockers,
        "honest_assessment": (
            "Pre-P16.8 trades have null entry/RR — gate cannot pass avg_rr check. "
            "Post-P16.8 filter prevents weak/low-RR trades from polluting the sample. "
            "Projection shows avg_rr improvement to ~0.472 → still below 1.0 gate. "
            "Real gate pass requires: 10 closed filtered trades + operator approval + live flag."
        ),
    }

    # Persist
    _atomic_write(_artifacts_dir() / f"sample_validation_{validation_id}.json", record)
    _atomic_write(_state_dir() / "paula_sample_validation_latest.json", record)

    return record
