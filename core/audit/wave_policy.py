"""AG-39: Repair Wave Policy.

Canonical wave policy definitions and constraint logic.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Default wave policy
# ---------------------------------------------------------------------------

DEFAULT_WAVE_POLICY: dict[str, Any] = {
    "max_items_per_wave": 3,
    "allow_target_overlap": False,
    "unstable_runtime_max_items": 1,
    "degraded_runtime_max_items": 2,
    "max_waves_per_run": 10,
    "p1_first": True,
}

# ---------------------------------------------------------------------------
# Priority bucket ordering (lower number = higher priority)
# ---------------------------------------------------------------------------

PRIORITY_BUCKET_ORDER: dict[str, int] = {
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
}

# ---------------------------------------------------------------------------
# Wave eligibility verdicts
# ---------------------------------------------------------------------------

WAVE_ELIGIBILITY_VERDICTS = {
    "ELIGIBLE":  "item is eligible for wave scheduling",
    "DEFER":     "item deferred — wave slot constraints not met",
    "BLOCK":     "item blocked — safety or overlap constraint violation",
    "ESCALATE":  "item requires operator review before scheduling",
}

# ---------------------------------------------------------------------------
# Wave states
# ---------------------------------------------------------------------------

WAVE_STATES = {
    "PROPOSED":            "wave proposed, awaiting operator approval",
    "APPROVED":            "operator approved — ready for execution handoff",
    "REJECTED":            "operator rejected — not scheduled",
    "READY_FOR_EXECUTION": "handoff to AG-34 authorized",
}


# ---------------------------------------------------------------------------
# Policy functions
# ---------------------------------------------------------------------------

def max_wave_size_for_stability(stability_classification: str, policy: dict[str, Any] | None = None) -> int:
    """Return max items per wave given current runtime stability classification.

    GOVERNANCE_RISK / UNSTABLE  → unstable_runtime_max_items (default 1)
    DEGRADED                    → degraded_runtime_max_items (default 2)
    All others                  → max_items_per_wave (default 3)
    """
    p = policy or DEFAULT_WAVE_POLICY
    cls = str(stability_classification).upper()
    if cls in ("GOVERNANCE_RISK", "UNSTABLE"):
        return int(p.get("unstable_runtime_max_items", 1))
    if cls == "DEGRADED":
        return int(p.get("degraded_runtime_max_items", 2))
    return int(p.get("max_items_per_wave", 3))


def can_items_share_wave(item_a: dict[str, Any], item_b: dict[str, Any], policy: dict[str, Any] | None = None) -> bool:
    """Return True if two queue items can safely share a wave.

    If allow_target_overlap is False (default), items touching the same
    component or plan_id may not share a wave.
    """
    p = policy or DEFAULT_WAVE_POLICY
    if p.get("allow_target_overlap", False):
        return True
    comp_a = str(item_a.get("component") or "")
    comp_b = str(item_b.get("component") or "")
    if comp_a and comp_b and comp_a == comp_b:
        return False
    plan_a = str(item_a.get("plan_id") or "")
    plan_b = str(item_b.get("plan_id") or "")
    if plan_a and plan_b and plan_a == plan_b:
        return False
    return True


def classify_wave_priority_bucket(priority_class: str) -> int:
    """Return integer bucket order for a priority class (1=highest)."""
    return PRIORITY_BUCKET_ORDER.get(str(priority_class).upper(), 99)
