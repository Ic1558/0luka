"""AG-38: Repair Priority Policy.

Canonical priority class definitions and scoring factor weights.
Pure data — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Priority classes
# ---------------------------------------------------------------------------

PRIORITY_CLASSES: dict[str, dict[str, Any]] = {
    "P1": {"min_score": 85, "meaning": "critical-first",  "description": "Immediate operator attention required"},
    "P2": {"min_score": 70, "meaning": "high-priority",   "description": "Next repair wave"},
    "P3": {"min_score": 50, "meaning": "normal",          "description": "Active backlog"},
    "P4": {"min_score": 0,  "meaning": "deferred",        "description": "Defer and observe"},
}

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

# Base score per governance status
STATUS_BASE_SCORE: dict[str, int] = {
    "ESCALATED":        50,
    "ESCALATED_AGAIN":  55,
    "OPEN":             30,
    "ACCEPTED":         15,
    "RESOLVED":         0,
    "DISMISSED":        0,
}

# Severity bonus
SEVERITY_BONUS: dict[str, int] = {
    "CRITICAL": 35,
    "HIGH":     25,
    "MEDIUM":   12,
    "LOW":      4,
    "INFO":     0,
}

# Pattern class bonus (operator gate regression is highest risk)
PATTERN_BONUS: dict[str, int] = {
    "recurring_operator_gate_regression": 30,
    "recurring_failed_repair_cycle":      22,
    "recurring_reconciliation_failure":   18,
    "recurring_route_surface_drift":      14,
    "recurring_state_file_absence":       10,
    "recurring_legacy_overlap":           8,
    "recurring_baseline_mismatch":        7,
    "recurring_naming_drift":             3,
}

# Failed repair history penalty (adds urgency — issue is hard to fix)
FAILED_REPAIR_URGENCY: dict[int, int] = {
    0: 0,
    1: 5,
    2: 10,
    3: 15,
}  # 3+ failed attempts → +15

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

def priority_reason_codes() -> dict[str, str]:
    return {
        "operator_gate_risk":       "finding involves operator gate regression — governance boundary risk",
        "recurring_pattern":        "finding is part of a recurring drift pattern",
        "hotspot_component":        "component is a known drift hotspot",
        "escalated_status":         "finding is ESCALATED or ESCALATED_AGAIN",
        "failed_repair_history":    "previous repair attempts for this finding have failed",
        "high_severity":            "finding has HIGH or CRITICAL severity",
        "stability_impact":         "finding contributes to runtime instability classification",
        "open_unaddressed":         "finding has been OPEN without governance action",
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_priority(score: int) -> str:
    """Return priority class string (P1..P4) for the given score."""
    for cls_name, entry in PRIORITY_CLASSES.items():
        if score >= entry["min_score"]:
            return cls_name
    return "P4"
