"""AG-44: Decision Queue Policy.

Queue priority classes, age rules, allowed status transitions, and scoring.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

import time
from typing import Any

# ---------------------------------------------------------------------------
# Queue priority classes
# ---------------------------------------------------------------------------

QUEUE_PRIORITY_CLASSES: dict[str, dict[str, Any]] = {
    "Q1": {"min_score": 80, "description": "Critical — immediate operator attention required"},
    "Q2": {"min_score": 60, "description": "High — address in current cycle"},
    "Q3": {"min_score": 40, "description": "Normal — active queue"},
    "Q4": {"min_score": 0,  "description": "Deferred — low urgency"},
}

# ---------------------------------------------------------------------------
# Queue status values and allowed transitions
# ---------------------------------------------------------------------------

QUEUE_STATUSES = {"OPEN", "DEFERRED", "STALE", "SUPERSEDED", "ARCHIVED"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "OPEN":       {"DEFERRED", "STALE", "SUPERSEDED", "ARCHIVED"},
    "DEFERRED":   {"OPEN", "STALE", "ARCHIVED"},
    "STALE":      {"OPEN", "ARCHIVED"},
    "SUPERSEDED": {"ARCHIVED"},
    "ARCHIVED":   set(),  # terminal
}

# ---------------------------------------------------------------------------
# Stale decision policy
# ---------------------------------------------------------------------------

STALE_DECISION_POLICY: dict[str, Any] = {
    "stale_after_seconds": 86400 * 3,   # 3 days
    "critical_stale_after_seconds": 86400,  # 1 day for CRITICAL/Q1
    "age_buckets": {
        "FRESH":   (0, 3600),        # < 1 hour
        "RECENT":  (3600, 86400),    # 1h – 24h
        "AGING":   (86400, 86400 * 3),  # 1d – 3d
        "STALE":   (86400 * 3, None),   # > 3d
    },
}

# ---------------------------------------------------------------------------
# Decision-type → base score weights
# ---------------------------------------------------------------------------

DECISION_TYPE_BASE_SCORE: dict[str, int] = {
    "PAUSE_NEW_CAMPAIGNS":           70,
    "REQUIRE_GOVERNANCE_REVIEW":     65,
    "ESCALATE_HIGH_RISK_COMPONENT":  60,
    "APPROVE_REPAIR_WAVE":           55,
    "DEFER_REPAIR_WAVE":             40,
    "REVIEW_PATTERN_REUSE":          35,
    "ACCEPT_BASELINE_PROPOSAL":      30,
    "REJECT_BASELINE_PROPOSAL":      30,
}

PRIORITY_SCORE_BONUS: dict[str, int] = {
    "CRITICAL": 25,
    "HIGH":     15,
    "MEDIUM":   5,
    "LOW":      0,
}

MODE_SCORE_BONUS: dict[str, int] = {
    "STABILIZE":        20,
    "HIGH_RISK_HOLD":   18,
    "GOVERNANCE_REVIEW": 12,
    "CONSERVATIVE":     8,
    "THROUGHPUT_LIMITED": 5,
    "PATTERN_REUSE_CANDIDATE": 3,
    "REPAIR_FOCUSED":   0,
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def classify_queue_priority_class(score: int) -> str:
    """Return Q1..Q4 for a priority score."""
    for cls, meta in QUEUE_PRIORITY_CLASSES.items():
        if score >= meta["min_score"]:
            return cls
    return "Q4"


def queue_priority_rank(name: str) -> int:
    """Return integer rank for a queue priority (lower = more urgent)."""
    order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    return order.get(name, 99)


def valid_queue_status_transition(old: str, new: str) -> bool:
    """Return True if transitioning from old → new is allowed."""
    return new in ALLOWED_TRANSITIONS.get(old, set())


def classify_age_bucket(ts: str | int | float) -> str:
    """Return age bucket string (FRESH / RECENT / AGING / STALE) from a timestamp.

    ts may be an ISO-8601 string ("2026-03-16T00:00:00Z") or a Unix timestamp (int/float).
    """
    now = time.time()
    if isinstance(ts, str):
        try:
            import time as _time
            age_secs = now - _time.mktime(_time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            age_secs = 0
    else:
        age_secs = max(0.0, now - float(ts))

    buckets = STALE_DECISION_POLICY["age_buckets"]
    for bucket_name, (lo, hi) in buckets.items():
        if hi is None:
            if age_secs >= lo:
                return bucket_name
        elif lo <= age_secs < hi:
            return bucket_name
    return "FRESH"


def score_queue_entry(package: dict[str, Any], operating_mode: str = "REPAIR_FOCUSED") -> int:
    """Compute a deterministic priority score for a queue entry."""
    dtype    = str(package.get("decision_type", ""))
    priority = str(package.get("priority", "MEDIUM")).upper()
    ts       = package.get("ts", "")

    base  = DECISION_TYPE_BASE_SCORE.get(dtype, 30)
    bonus = PRIORITY_SCORE_BONUS.get(priority, 0)
    mode_bonus = MODE_SCORE_BONUS.get(operating_mode.upper(), 0)

    # Aging bonus — stale decisions get a bump so operator notices
    age_bucket = classify_age_bucket(ts)
    age_bonus  = {"FRESH": 0, "RECENT": 3, "AGING": 8, "STALE": 15}.get(age_bucket, 0)

    return min(100, base + bonus + mode_bonus + age_bonus)
