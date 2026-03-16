"""AG-48: Runtime Claim Verifier Policy.

Verdict classes, readiness verification rules, posture verification rules,
and helper functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Claim verdict classes
# ---------------------------------------------------------------------------

CLAIM_VERDICTS = ["VERIFIED", "UNSUPPORTED", "INCONSISTENT", "INCONCLUSIVE"]

CLAIM_VERDICT_META: dict[str, str] = {
    "VERIFIED":     "Claimed value matches observed evidence",
    "UNSUPPORTED":  "No evidence found to support the claim",
    "INCONSISTENT": "Evidence contradicts the claim",
    "INCONCLUSIVE": "Evidence present but insufficient to confirm or deny",
}

# ---------------------------------------------------------------------------
# Canonical identity constants
# ---------------------------------------------------------------------------

CANONICAL_SYSTEM_IDENTITY = "Supervised Agentic Runtime Platform"
CANONICAL_RUNTIME_ROLE    = "governed execution + supervised repair + advisory intelligence"

# ---------------------------------------------------------------------------
# Readiness verification rules
# ---------------------------------------------------------------------------
# Each rule maps to minimum conditions that must hold for a readiness claim
# to be VERIFIED.

READINESS_VERIFICATION_RULES: dict[str, dict[str, Any]] = {
    "LIMITED": {
        "required_conditions": [],   # always satisfiable — floor class
        "description": "No active capabilities needed",
    },
    "PARTIAL": {
        "required_conditions": ["active_capability_count_ge_2"],
        "description": "At least 2 active capabilities",
    },
    "OPERATIONAL": {
        "required_conditions": ["active_capability_count_ge_4"],
        "description": "At least 4 active capabilities",
    },
    "SUPERVISED_READY": {
        "required_conditions": [
            "active_capability_count_ge_6",
            "strategy_active",
            "repair_active",
        ],
        "description": "6+ capabilities, strategy and repair active",
    },
    "GOVERNED_READY": {
        "required_conditions": [
            "active_capability_count_ge_8",
            "strategy_active",
            "governance_active",
            "decision_queue_active",
        ],
        "description": "8+ capabilities, strategy + governance + decision queue active",
    },
}

# ---------------------------------------------------------------------------
# Posture verification rules
# ---------------------------------------------------------------------------

POSTURE_VERIFICATION_RULES: dict[str, dict[str, str]] = {
    "OPERATOR_GATED": {
        "evidence_key": "operator_action_required",
        "expected":     "true",
        "description":  "operator_action_required must be true in decision state",
    },
    "CAMPAIGN_CONTROLLED": {
        "evidence_key": "campaign_present",
        "expected":     "true",
        "description":  "campaign state must be present",
    },
    "SUPERVISED_REPAIR_AVAILABLE": {
        "evidence_key": "repair_execution_available",
        "expected":     "true",
        "description":  "repair plan or execution evidence must be present",
    },
    "QUEUE_GOVERNED": {
        "evidence_key": "queue_governance_present",
        "expected":     "true",
        "description":  "decision_queue_governance_latest.json must exist",
    },
    "STRATEGY_ADVISORY": {
        "evidence_key": "strategy_present",
        "expected":     "true",
        "description":  "runtime_strategy_latest.json must exist",
    },
    "CAMPAIGN_ADVISORY": {
        "evidence_key": "outcome_intel_present",
        "expected":     "true",
        "description":  "campaign outcome intelligence must be present",
    },
    "REPAIR_PLANNING_ONLY": {
        "evidence_key": "repair_plan_present",
        "expected":     "true",
        "description":  "repair plan must be present",
    },
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def valid_claim_verdict(name: str) -> bool:
    """Return True if name is a registered claim verdict."""
    return name in CLAIM_VERDICTS


def verify_readiness_rule(claimed: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Verify whether the claimed readiness class is supported by evidence.

    evidence keys (all optional):
      active_capability_count: int
      strategy_active: bool
      governance_active: bool
      decision_queue_active: bool
      repair_active: bool

    Returns a result dict with verdict, claimed, observed_conditions, and evidence_refs.
    """
    rule = READINESS_VERIFICATION_RULES.get(claimed)
    if rule is None:
        return {
            "claimed": claimed,
            "verdict": "INCONCLUSIVE",
            "reason":  f"no verification rule for readiness class {claimed!r}",
            "evidence_refs": [],
        }

    active_caps = int(evidence.get("active_capability_count", 0))
    strategy_ok   = bool(evidence.get("strategy_active", False))
    governance_ok = bool(evidence.get("governance_active", False))
    decision_ok   = bool(evidence.get("decision_queue_active", False))
    repair_ok     = bool(evidence.get("repair_active", False))

    required = rule["required_conditions"]
    failed: list[str] = []

    for cond in required:
        if cond == "active_capability_count_ge_2" and active_caps < 2:
            failed.append(f"active_capability_count={active_caps} < 2")
        elif cond == "active_capability_count_ge_4" and active_caps < 4:
            failed.append(f"active_capability_count={active_caps} < 4")
        elif cond == "active_capability_count_ge_6" and active_caps < 6:
            failed.append(f"active_capability_count={active_caps} < 6")
        elif cond == "active_capability_count_ge_8" and active_caps < 8:
            failed.append(f"active_capability_count={active_caps} < 8")
        elif cond == "strategy_active" and not strategy_ok:
            failed.append("strategy layer not active")
        elif cond == "governance_active" and not governance_ok:
            failed.append("governance state absent")
        elif cond == "decision_queue_active" and not decision_ok:
            failed.append("decision queue governance absent")
        elif cond == "repair_active" and not repair_ok:
            failed.append("repair layer not active")

    if not required:
        verdict = "VERIFIED"
        reason  = "floor readiness class — always satisfiable"
    elif failed:
        # Determine whether evidence is absent (UNSUPPORTED) or contradicts (INCONSISTENT)
        # If capabilities are 0 — unsupported. If capabilities exist but lower — inconsistent.
        if active_caps == 0 and all("active_capability_count" in f for f in failed):
            verdict = "UNSUPPORTED"
        else:
            verdict = "INCONSISTENT"
        reason = "; ".join(failed)
    else:
        verdict = "VERIFIED"
        reason  = "all required conditions met"

    return {
        "claimed":     claimed,
        "verdict":     verdict,
        "reason":      reason,
        "failed_conditions": failed,
        "evidence_refs": ["runtime_capabilities.jsonl", "runtime_strategy_latest.json"],
    }


def verify_posture_rule(
    claim_key: str,
    claimed: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Verify a single posture claim against evidence.

    claim_key: posture dimension (e.g. "governance_posture")
    claimed:   the claimed class (e.g. "OPERATOR_GATED")
    evidence:  flat dict with boolean/int signals

    Returns a result dict with verdict, claimed, observed, and evidence_refs.
    """
    rule = POSTURE_VERIFICATION_RULES.get(claimed)
    if rule is None:
        # Unknown posture class — inconclusive
        return {
            "claim_key": claim_key,
            "claimed":   claimed,
            "verdict":   "INCONCLUSIVE",
            "reason":    f"no verification rule for posture class {claimed!r}",
            "evidence_refs": [],
        }

    ev_key   = rule["evidence_key"]
    observed = evidence.get(ev_key)

    if observed is None:
        verdict = "UNSUPPORTED"
        reason  = f"evidence key {ev_key!r} not found in evidence"
    elif bool(observed) is True:
        verdict = "VERIFIED"
        reason  = f"{ev_key}=true matches {claimed!r}"
    else:
        verdict = "INCONSISTENT"
        reason  = f"{ev_key}=false contradicts {claimed!r}"

    return {
        "claim_key":   claim_key,
        "claimed":     claimed,
        "observed":    observed,
        "verdict":     verdict,
        "reason":      reason,
        "evidence_refs": [_evidence_file_for(ev_key)],
    }


def _evidence_file_for(ev_key: str) -> str:
    mapping = {
        "operator_action_required": "decision_queue_governance_latest.json",
        "campaign_present":         "repair_campaign_latest.json",
        "repair_execution_available": "drift_repair_execution_log.jsonl",
        "queue_governance_present": "decision_queue_governance_latest.json",
        "strategy_present":         "runtime_strategy_latest.json",
        "outcome_intel_present":    "repair_campaign_outcome_latest.json",
        "repair_plan_present":      "drift_repair_plan_latest.json",
    }
    return mapping.get(ev_key, "runtime_self_awareness_latest.json")
