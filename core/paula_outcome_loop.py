"""
paula_outcome_loop.py — Closed-loop trading intelligence from Paula outcomes.

Invariants:
  - No auto-trade, no auto-promotion
  - Read-only intelligence: ingest → analyze → suggest → candidate
  - review_required=True on all candidates

Output contract:
  {
    "outcome_status": "win" | "loss" | "neutral" | "unknown",
    "hindsight_summary": str,
    "suggestion_summary": str,
    "candidate_count": int,
    "review_required": bool,
    "loop_id": str,
  }
"""

import uuid


_OUTCOME_PATTERNS = {
    "win": {
        "hindsight_summary": "Outcome positive — strategy executed as intended.",
        "suggestion_summary": "Reinforce this pattern: reuse skill/routing for similar signal.",
        "severity": "positive",
    },
    "loss": {
        "hindsight_summary": "Outcome negative — execution or signal may have been suboptimal.",
        "suggestion_summary": (
            "Review entry timing and signal confidence. "
            "Consider tighter stop or lower position size on next occurrence."
        ),
        "severity": "negative",
    },
    "neutral": {
        "hindsight_summary": "Outcome neutral — no strong signal for reinforcement or correction.",
        "suggestion_summary": "Continue accumulating samples before adjusting strategy.",
        "severity": "neutral",
    },
    "unknown": {
        "hindsight_summary": "Outcome unknown — insufficient data to classify.",
        "suggestion_summary": "Operator review required before any strategy adjustment.",
        "severity": "inconclusive",
    },
}


def _classify_outcome(outcome: dict) -> str:
    """Classify outcome dict into win/loss/neutral/unknown."""
    # Accept both "outcome" (operator-facing) and "status" (internal) keys
    raw = outcome.get("outcome") or outcome.get("status") or "unknown"
    status = raw.lower()
    pnl = outcome.get("pnl")

    if status in ("win", "profit", "success"):
        return "win"
    if status in ("loss", "losing", "failed"):
        return "loss"
    if status == "neutral":
        return "neutral"

    # fallback: classify by pnl if present
    if pnl is not None:
        try:
            pnl_val = float(pnl)
            if pnl_val > 0:
                return "win"
            if pnl_val < 0:
                return "loss"
            return "neutral"
        except (TypeError, ValueError):
            pass

    return "unknown"


def ingest_outcome(outcome: dict) -> dict:
    """
    Ingest a Paula trade outcome and produce closed-loop learning artifacts.

    Args:
        outcome: Dict describing the Paula trade result. Expected keys:
                 - status: "win" | "loss" | "neutral" (required)
                 - symbol: str (optional)
                 - pnl: float (optional)
                 - trace_id: str (optional — source trace for linkage)
                 - signal_confidence: float (optional)

    Returns:
        Structured loop output with hindsight + suggestion + candidate.
    """
    loop_id = str(uuid.uuid4())[:8]
    outcome_class = _classify_outcome(outcome)
    pattern = _OUTCOME_PATTERNS[outcome_class]

    symbol = outcome.get("symbol", "unknown")
    trace_id = outcome.get("trace_id")
    signal_confidence = outcome.get("signal_confidence")

    # build candidate (review-required, no auto-promotion)
    candidate = {
        "loop_id": loop_id,
        "auto_promotion": False,
        "source_trace_id": trace_id,
        "outcome_class": outcome_class,
        "symbol": symbol,
        "proposed_adjustment": pattern["suggestion_summary"],
        "review_required": True,
    }
    if signal_confidence is not None:
        candidate["signal_confidence"] = signal_confidence

    review_required = outcome_class in ("loss", "unknown")

    return {
        "outcome_status": outcome_class,
        "hindsight_summary": pattern["hindsight_summary"],
        "suggestion_summary": pattern["suggestion_summary"],
        "candidate_count": 1,
        "candidates": [candidate],
        "review_required": review_required,
        "loop_id": loop_id,
        "auto_promotion": False,
    }
