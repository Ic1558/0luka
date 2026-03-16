"""AG-47: Runtime Self-Awareness Policy.

Readiness classes, posture mappings, and classification helpers.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Readiness classes (ordered, worst → best)
# ---------------------------------------------------------------------------

READINESS_CLASSES = ["LIMITED", "PARTIAL", "OPERATIONAL", "SUPERVISED_READY", "GOVERNED_READY"]

READINESS_CLASS_META: dict[str, dict[str, Any]] = {
    "LIMITED": {
        "description": "Core capabilities absent — runtime cannot meaningfully operate",
        "min_active_capabilities": 0,
    },
    "PARTIAL": {
        "description": "Some capabilities active but governance or repair stack incomplete",
        "min_active_capabilities": 2,
    },
    "OPERATIONAL": {
        "description": "Core execution + audit capabilities active",
        "min_active_capabilities": 4,
    },
    "SUPERVISED_READY": {
        "description": "Supervised repair chain active; strategy layer present",
        "min_active_capabilities": 6,
    },
    "GOVERNED_READY": {
        "description": "Full stack active: execution + governance + strategy + decision governance",
        "min_active_capabilities": 8,
    },
}

# ---------------------------------------------------------------------------
# Posture classes
# ---------------------------------------------------------------------------

GOVERNANCE_POSTURE_CLASSES = {
    "OPERATOR_GATED":     "All governance actions require explicit operator approval",
    "ADVISORY_ONLY":      "Governance recommendations generated; operator not prompted",
    "GOVERNANCE_ABSENT":  "No governance state detected",
}

REPAIR_POSTURE_CLASSES = {
    "SUPERVISED_REPAIR_AVAILABLE": "Supervised repair chain present and operable",
    "REPAIR_PLANNING_ONLY":        "Repair planning active; execution not available",
    "REPAIR_ABSENT":               "No repair capability detected",
}

CAMPAIGN_POSTURE_CLASSES = {
    "CAMPAIGN_CONTROLLED": "Campaign creation/execution supervised by operator",
    "CAMPAIGN_ADVISORY":   "Campaign intelligence active but no execution control",
    "CAMPAIGN_ABSENT":     "No campaign state detected",
}

DECISION_POSTURE_CLASSES = {
    "QUEUE_GOVERNED":     "Decision queue governance active; lifecycle transitions available",
    "DECISION_ASSIST":    "Decision assist active; no queue governance",
    "DECISION_ABSENT":    "No decision governance detected",
}

STRATEGY_POSTURE_CLASSES = {
    "STRATEGY_ADVISORY":   "Runtime strategy layer active; recommendations available",
    "STRATEGY_ABSENT":     "No strategy layer detected",
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def classify_readiness(inputs: dict[str, Any]) -> str:
    """Derive readiness class from available runtime signals.

    inputs keys (all optional):
      active_capability_count: int
      strategy_active: bool
      governance_active: bool
      decision_queue_active: bool
      repair_active: bool
      operating_mode: str
    """
    active_caps   = int(inputs.get("active_capability_count", 0))
    strategy_ok   = bool(inputs.get("strategy_active", False))
    governance_ok = bool(inputs.get("governance_active", False))
    decision_ok   = bool(inputs.get("decision_queue_active", False))
    repair_ok     = bool(inputs.get("repair_active", False))

    if active_caps >= 8 and strategy_ok and governance_ok and decision_ok:
        return "GOVERNED_READY"
    if active_caps >= 6 and strategy_ok and repair_ok:
        return "SUPERVISED_READY"
    if active_caps >= 4:
        return "OPERATIONAL"
    if active_caps >= 2:
        return "PARTIAL"
    return "LIMITED"


def classify_governance_posture(inputs: dict[str, Any]) -> str:
    """Derive governance posture class.

    inputs keys (all optional):
      governance_findings_count: int
      operator_action_required: bool
    """
    if inputs.get("operator_action_required", False):
        return "OPERATOR_GATED"
    if int(inputs.get("governance_findings_count", 0)) > 0:
        return "ADVISORY_ONLY"
    return "GOVERNANCE_ABSENT"


def classify_repair_posture(inputs: dict[str, Any]) -> str:
    """Derive repair posture class.

    inputs keys (all optional):
      repair_plan_present: bool
      repair_execution_available: bool
    """
    if inputs.get("repair_execution_available", False):
        return "SUPERVISED_REPAIR_AVAILABLE"
    if inputs.get("repair_plan_present", False):
        return "REPAIR_PLANNING_ONLY"
    return "REPAIR_ABSENT"
