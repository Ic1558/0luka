"""AG-43: Decision Package Policy.

Canonical decision type definitions, priority classification,
and strategy-recommendation-to-decision-type mapping.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Decision types
# ---------------------------------------------------------------------------

DECISION_TYPES: dict[str, dict[str, Any]] = {
    "APPROVE_REPAIR_WAVE": {
        "description": "Approve a PROPOSED repair wave for execution handoff to AG-34",
        "default_priority": "HIGH",
        "alternatives": ["DEFER_REPAIR_WAVE"],
    },
    "DEFER_REPAIR_WAVE": {
        "description": "Defer a PROPOSED repair wave — do not execute in current cycle",
        "default_priority": "MEDIUM",
        "alternatives": ["APPROVE_REPAIR_WAVE"],
    },
    "PAUSE_NEW_CAMPAIGNS": {
        "description": "Pause creation of new repair campaigns until risks are resolved",
        "default_priority": "HIGH",
        "alternatives": ["REQUIRE_GOVERNANCE_REVIEW"],
    },
    "REVIEW_PATTERN_REUSE": {
        "description": "Review a campaign pattern before authorising its reuse",
        "default_priority": "MEDIUM",
        "alternatives": ["APPROVE_REPAIR_WAVE", "DEFER_REPAIR_WAVE"],
    },
    "ACCEPT_BASELINE_PROPOSAL": {
        "description": "Accept an AG-36 baseline realignment proposal",
        "default_priority": "MEDIUM",
        "alternatives": ["REJECT_BASELINE_PROPOSAL"],
    },
    "REJECT_BASELINE_PROPOSAL": {
        "description": "Reject an AG-36 baseline realignment proposal",
        "default_priority": "MEDIUM",
        "alternatives": ["ACCEPT_BASELINE_PROPOSAL"],
    },
    "ESCALATE_HIGH_RISK_COMPONENT": {
        "description": "Escalate a high-risk component for immediate operator review",
        "default_priority": "HIGH",
        "alternatives": ["REQUIRE_GOVERNANCE_REVIEW"],
    },
    "REQUIRE_GOVERNANCE_REVIEW": {
        "description": "Require a governance lifecycle review before any repair action",
        "default_priority": "HIGH",
        "alternatives": ["ESCALATE_HIGH_RISK_COMPONENT"],
    },
}

# ---------------------------------------------------------------------------
# Strategy recommendation → decision type mapping
# ---------------------------------------------------------------------------

RECOMMENDATION_TO_DECISION_TYPE: dict[str, str] = {
    "CONTINUE_REPAIR_WAVE":         "APPROVE_REPAIR_WAVE",
    "PAUSE_NEW_CAMPAIGNS":          "PAUSE_NEW_CAMPAIGNS",
    "REDUCE_WAVE_SIZE":             "DEFER_REPAIR_WAVE",
    "REVIEW_PATTERN_BEFORE_REUSE":  "REVIEW_PATTERN_REUSE",
    "ISOLATE_HIGH_RISK_COMPONENTS": "ESCALATE_HIGH_RISK_COMPONENT",
    "PRIORITIZE_GOVERNANCE_FIXES":  "REQUIRE_GOVERNANCE_REVIEW",
    "INCREASE_REPAIR_THROUGHPUT":   "APPROVE_REPAIR_WAVE",
    "REVIEW_FAILED_CAMPAIGNS":      "REVIEW_PATTERN_REUSE",
}

# ---------------------------------------------------------------------------
# Priority levels
# ---------------------------------------------------------------------------

DECISION_PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def valid_decision_type(name: str) -> bool:
    """Return True if name is a registered decision type."""
    return name in DECISION_TYPES


def recommendation_to_decision_type(recommendation: str) -> str | None:
    """Map a strategy recommendation class to a decision type. Returns None if unknown."""
    return RECOMMENDATION_TO_DECISION_TYPE.get(recommendation)


def classify_decision_priority(inputs: dict[str, Any]) -> str:
    """Classify the priority of a decision candidate.

    Inputs (all optional):
      operating_mode: str
      p1_count: int
      active_regressions: int
      high_risk_patterns: int
      decision_type: str
    """
    mode        = str(inputs.get("operating_mode", "REPAIR_FOCUSED")).upper()
    p1_count    = int(inputs.get("p1_count", 0))
    regressions = int(inputs.get("active_regressions", 0))
    high_risk   = int(inputs.get("high_risk_patterns", 0))
    dtype       = str(inputs.get("decision_type", ""))

    # Critical: system in crisis or high-risk hold
    if mode in ("STABILIZE", "HIGH_RISK_HOLD") and dtype in (
        "PAUSE_NEW_CAMPAIGNS", "REQUIRE_GOVERNANCE_REVIEW", "ESCALATE_HIGH_RISK_COMPONENT"
    ):
        return "CRITICAL"

    # High: regressions active, or P1 backlog large, or high-risk patterns
    if regressions >= 2 or (p1_count >= 5 and dtype == "APPROVE_REPAIR_WAVE") or high_risk >= 1:
        return "HIGH"

    # Return default from decision type definition
    return DECISION_TYPES.get(dtype, {}).get("default_priority", "MEDIUM")
