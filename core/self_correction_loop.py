"""
self_correction_loop.py — Proposes structured corrections for failed/rejected traces.

Invariants:
  - No automatic execution
  - No bypass of skill safety
  - retry_allowed=False for all destructive cases
  - review_required=True when confidence < 0.6

Output contract:
  {
    "trace_id": str,
    "correction_type": "rephrase" | "scope_down" | "operator_review" | "no_correction",
    "original_issue": str,
    "corrected_intent": str | None,
    "retry_allowed": bool,
    "review_required": bool,
    "confidence": float,
  }
"""

from core.hindsight_engine import analyze_trace


_CORRECTION_MAP = {
    "destructive_intent": {
        "correction_type": "scope_down",
        "corrected_intent": "Scope down the request to a non-destructive action, or confirm with operator",
        "retry_allowed": False,
        "review_required": True,
        "confidence": 0.9,
    },
    "unknown_intent": {
        "correction_type": "rephrase",
        "corrected_intent": "Rephrase as verb + object (e.g. 'list files', 'check health')",
        "retry_allowed": True,
        "review_required": False,
        "confidence": 0.75,
    },
    "unknown_rejection": {
        "correction_type": "operator_review",
        "corrected_intent": None,
        "retry_allowed": False,
        "review_required": True,
        "confidence": 0.5,
    },
    "trace_corruption": {
        "correction_type": "operator_review",
        "corrected_intent": "Re-run the original operation from scratch",
        "retry_allowed": False,
        "review_required": True,
        "confidence": 1.0,
    },
    "snapshot_corruption": {
        "correction_type": "operator_review",
        "corrected_intent": "Re-run the original operation from scratch",
        "retry_allowed": False,
        "review_required": True,
        "confidence": 1.0,
    },
    "unsupported_trace_version": {
        "correction_type": "operator_review",
        "corrected_intent": "Upgrade trace version or re-run with current version",
        "retry_allowed": False,
        "review_required": True,
        "confidence": 1.0,
    },
}


def correct_from_trace(trace_id: str) -> dict:
    """
    Propose a structured correction for a failed/rejected trace.

    Args:
        trace_id: The trace_id to analyze and correct.

    Returns:
        Structured correction proposal.
    """
    hindsight = analyze_trace(trace_id)
    findings = hindsight.get("findings") or {}
    root = findings.get("failure_root_cause")

    if not root:
        return {
            "trace_id": trace_id,
            "correction_type": "no_correction",
            "original_issue": "no failure detected",
            "corrected_intent": None,
            "retry_allowed": True,
            "review_required": False,
            "confidence": 1.0,
        }

    correction = _CORRECTION_MAP.get(root, _CORRECTION_MAP["unknown_rejection"])

    return {
        "trace_id": trace_id,
        "correction_type": correction["correction_type"],
        "original_issue": root,
        "corrected_intent": correction["corrected_intent"],
        "retry_allowed": correction["retry_allowed"],
        "review_required": correction["review_required"] or correction["confidence"] < 0.6,
        "confidence": correction["confidence"],
    }


def correct_from_result(result: dict) -> dict:
    """
    Propose a structured correction from a direct result dict.

    Args:
        result: Dict with at least "status" and optionally "reason" and "trace_id".

    Returns:
        Structured correction proposal.
    """
    status = result.get("status", "unknown")
    reason = result.get("reason", "unknown_rejection")
    trace_id = result.get("trace_id", "unknown")

    if status not in ("rejected", "blocked", "failed"):
        return {
            "trace_id": trace_id,
            "correction_type": "no_correction",
            "original_issue": f"status={status} — not a failure",
            "corrected_intent": None,
            "retry_allowed": True,
            "review_required": False,
            "confidence": 1.0,
        }

    correction = _CORRECTION_MAP.get(reason, _CORRECTION_MAP["unknown_rejection"])

    return {
        "trace_id": trace_id,
        "correction_type": correction["correction_type"],
        "original_issue": reason,
        "corrected_intent": correction["corrected_intent"],
        "retry_allowed": correction["retry_allowed"],
        "review_required": correction["review_required"],
        "confidence": correction["confidence"],
    }
