"""AG-P15: Paula Performance Aggregation + Strategy Scoring."""
from __future__ import annotations
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


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


# ── Load ─────────────────────────────────────────────────────────────────────
def load_trade_artifacts() -> list[dict]:
    """Glob all paula_paper_*.json from the runtime artifacts dir. Skip malformed."""
    artifacts_dir = _artifacts_dir()
    trades = []
    for p in sorted(artifacts_dir.glob("paula_paper_*.json")):
        try:
            d = json.loads(p.read_text())
            if "paper_trade_id" not in d or "status" not in d:
                continue
            trades.append(d)
        except Exception:
            continue
    return trades


# ── Metrics ──────────────────────────────────────────────────────────────────
CLOSED_STATUSES = {"closed_tp", "closed_sl", "closed_manual", "expired"}


def compute_metrics(trades: list[dict]) -> dict:
    """Aggregate trade list into performance metrics. Malformed entries are skipped."""
    skipped = 0
    valid: list[dict] = []
    for t in trades:
        if not isinstance(t, dict) or "paper_trade_id" not in t or "status" not in t:
            skipped += 1
            continue
        valid.append(t)

    closed = [t for t in valid if t["status"] in CLOSED_STATUSES]
    open_trades = [t for t in valid if t["status"] not in CLOSED_STATUSES]

    wins = [t for t in closed if (t.get("pnl") or {}).get("result") == "win"]
    losses = [t for t in closed if (t.get("pnl") or {}).get("result") == "loss"]
    neutrals = [t for t in closed if (t.get("pnl") or {}).get("result") == "neutral"]

    rr_vals = [
        t["pnl"]["rr"]
        for t in closed
        if (t.get("pnl") or {}).get("rr") is not None
    ]

    win_rate = round(len(wins) / len(closed), 3) if closed else None
    avg_rr = round(sum(rr_vals) / len(rr_vals), 3) if rr_vals else None

    # TP / SL hit counts
    tp_hit_counts: dict[str, int] = {"TP1": 0, "TP2": 0, "TP3": 0}
    sl_hit_count = 0
    expired_count = 0
    for t in closed:
        pnl = t.get("pnl") or {}
        hit = pnl.get("hit_tp")
        if hit in tp_hit_counts:
            tp_hit_counts[hit] += 1
        if pnl.get("hit_sl"):
            sl_hit_count += 1
        if t["status"] == "expired":
            expired_count += 1

    # By-symbol breakdown
    by_symbol: dict[str, dict] = {}
    for t in closed:
        sym = t.get("symbol", "UNKNOWN")
        if sym not in by_symbol:
            by_symbol[sym] = {"total": 0, "wins": 0, "losses": 0, "win_rate": None}
        by_symbol[sym]["total"] += 1
        pnl_result = (t.get("pnl") or {}).get("result")
        if pnl_result == "win":
            by_symbol[sym]["wins"] += 1
        elif pnl_result == "loss":
            by_symbol[sym]["losses"] += 1
    for sym, s in by_symbol.items():
        s["win_rate"] = round(s["wins"] / s["total"], 3) if s["total"] else None

    # By-direction breakdown
    by_direction: dict[str, dict] = {}
    for t in closed:
        direction = t.get("direction", "UNKNOWN")
        if direction not in by_direction:
            by_direction[direction] = {"total": 0, "wins": 0, "losses": 0, "win_rate": None}
        by_direction[direction]["total"] += 1
        pnl_result = (t.get("pnl") or {}).get("result")
        if pnl_result == "win":
            by_direction[direction]["wins"] += 1
        elif pnl_result == "loss":
            by_direction[direction]["losses"] += 1
    for direction, s in by_direction.items():
        s["win_rate"] = round(s["wins"] / s["total"], 3) if s["total"] else None

    return {
        "total_trades": len(valid),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "wins": len(wins),
        "losses": len(losses),
        "neutrals": len(neutrals),
        "win_rate": win_rate,
        "avg_rr": avg_rr,
        "tp_hit_counts": tp_hit_counts,
        "sl_hit_count": sl_hit_count,
        "expired_count": expired_count,
        "skipped_malformed": skipped,
        "by_symbol": by_symbol,
        "by_direction": by_direction,
    }


# ── Strategy Score ────────────────────────────────────────────────────────────
def compute_strategy_score(metrics: dict) -> dict:
    """Derive a simple strategy quality label from aggregated metrics."""
    closed = metrics["closed_trades"]
    wr = metrics["win_rate"]
    rr = metrics["avg_rr"]

    if closed < 3:
        score = "insufficient_data"
    elif wr >= 0.5 and (rr is None or rr >= 1.0):
        score = "positive"
    elif wr < 0.3:
        score = "negative"
    else:
        score = "mixed"

    return {
        "strategy_score": score,
        "score_basis": {"win_rate": wr, "avg_rr": rr, "sample_size": closed},
    }


# ── Main entry ────────────────────────────────────────────────────────────────
def run_paula_performance(operator_id: str = "boss") -> dict:
    """Load all paper trades, compute metrics + strategy score, persist results."""
    ts = _now()
    hex8 = secrets.token_hex(4)
    trace_id = f"trace_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    perf_id = f"paula_perf_{hex8}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    trades = load_trade_artifacts()
    metrics = compute_metrics(trades)
    scoring = compute_strategy_score(metrics)

    result: dict = {
        "perf_id": perf_id,
        "operator_id": operator_id,
        "ts": ts,
        "governed": True,
        **metrics,
        **scoring,
    }

    # Atomic write: latest state
    _atomic_write(_state_dir() / "paula_performance_latest.json", result)

    # Append to log
    _atomic_append(_state_dir() / "paula_performance_log.jsonl", result)

    # Artifact copy
    _atomic_write(_artifacts_dir() / f"perf_{trace_id}.json", result)

    return result
