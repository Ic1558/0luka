"""AG-45: Decision Memory Policy.

Recurrence classes, memory thresholds, and contextualization rules.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Recurrence pattern classes
# ---------------------------------------------------------------------------

MEMORY_PATTERNS: dict[str, dict[str, Any]] = {
    "repeated_deferral_pattern": {
        "description": "Decision of this type/target has been deferred multiple times",
        "threshold": 2,   # occurrences to trigger
    },
    "repeated_supersede_pattern": {
        "description": "Decision of this type/target has been superseded multiple times",
        "threshold": 2,
    },
    "recurring_high_risk_component_decision": {
        "description": "High-risk component decisions keep surfacing for the same target",
        "threshold": 2,
    },
    "recurring_governance_review_requirement": {
        "description": "Governance review requirement keeps being raised for the same target",
        "threshold": 2,
    },
    "stale_decision_reopen_pattern": {
        "description": "Decision has gone stale and been reopened repeatedly",
        "threshold": 1,
    },
    "repeated_pause_campaign_recommendation": {
        "description": "Campaign pause recommendation keeps recurring across sessions",
        "threshold": 2,
    },
}

# Decision types that signal high-risk components
HIGH_RISK_DECISION_TYPES = {"ESCALATE_HIGH_RISK_COMPONENT", "REQUIRE_GOVERNANCE_REVIEW"}

# Decision types that map to governance review recurrence
GOVERNANCE_REVIEW_TYPES = {"REQUIRE_GOVERNANCE_REVIEW", "ESCALATE_HIGH_RISK_COMPONENT"}

# Decision types that map to campaign pause recurrence
PAUSE_CAMPAIGN_TYPES = {"PAUSE_NEW_CAMPAIGNS"}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def valid_memory_pattern(name: str) -> bool:
    """Return True if name is a registered memory pattern."""
    return name in MEMORY_PATTERNS


def recurrence_threshold_for(name: str) -> int:
    """Return the minimum occurrence count to flag as a recurrence pattern."""
    return MEMORY_PATTERNS.get(name, {}).get("threshold", 2)


def should_attach_memory_context(decision: dict[str, Any], memory_entry: dict[str, Any]) -> bool:
    """Return True if a memory entry is relevant to attach to an open decision.

    Attachment is appropriate when the memory entry's decision_type or
    target_ref matches the current decision.
    """
    if decision.get("decision_type") == memory_entry.get("decision_type"):
        return True
    # Same target reference — different decision types may also be relevant
    dec_target = str(decision.get("target_ref", "")).strip()
    mem_target = str(memory_entry.get("target_ref", "")).strip()
    if dec_target and dec_target == mem_target:
        return True
    return False
