"""AG-42: Supervisory Runtime Strategy Policy.

Canonical operating mode definitions, signal-to-mode mapping,
and recommendation priority ordering.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Operating modes
# ---------------------------------------------------------------------------

OPERATING_MODES: dict[str, dict[str, Any]] = {
    "STABILIZE": {
        "description": "System is destabilized — stabilize before new repair activity",
        "priority": 1,
        "signals": ["governance_risk", "high_regression_count", "critical_stability_score"],
    },
    "HIGH_RISK_HOLD": {
        "description": "Multiple regression signals — hold new campaigns until resolved",
        "priority": 2,
        "signals": ["active_regressions", "high_intervention_burden", "abort_prone_patterns"],
    },
    "GOVERNANCE_REVIEW": {
        "description": "Governance risk elevated — operator review of finding lifecycle required",
        "priority": 3,
        "signals": ["escalated_finding_count", "governance_risk_classification", "unresolved_criticals"],
    },
    "CONSERVATIVE": {
        "description": "Proceed carefully — reduce blast radius and wave size",
        "priority": 4,
        "signals": ["degraded_stability", "recent_failures", "high_campaign_failure_rate"],
    },
    "THROUGHPUT_LIMITED": {
        "description": "Repair activity is limited by stability or policy constraints",
        "priority": 5,
        "signals": ["low_stability_score", "large_backlog", "wave_size_constrained"],
    },
    "PATTERN_REUSE_CANDIDATE": {
        "description": "Successful campaign patterns identified — reuse opportunity",
        "priority": 6,
        "signals": ["repeatable_success_pattern", "high_effectiveness_score", "low_regression_count"],
    },
    "REPAIR_FOCUSED": {
        "description": "System is stable enough for focused repair throughput",
        "priority": 7,
        "signals": ["stable_classification", "low_p1_count", "low_regression_count"],
    },
}

# ---------------------------------------------------------------------------
# Strategy recommendation classes
# ---------------------------------------------------------------------------

STRATEGY_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "CONTINUE_REPAIR_WAVE": {
        "description": "Current repair wave cadence is effective — continue",
        "severity": "LOW",
    },
    "PAUSE_NEW_CAMPAIGNS": {
        "description": "Pause new campaign creation until regressions resolved",
        "severity": "HIGH",
    },
    "REDUCE_WAVE_SIZE": {
        "description": "Reduce wave size to limit blast radius in degraded runtime",
        "severity": "MEDIUM",
    },
    "REVIEW_PATTERN_BEFORE_REUSE": {
        "description": "Review campaign pattern before scheduling next wave",
        "severity": "MEDIUM",
    },
    "ISOLATE_HIGH_RISK_COMPONENTS": {
        "description": "Quarantine high-risk components from repair wave overlap",
        "severity": "HIGH",
    },
    "PRIORITIZE_GOVERNANCE_FIXES": {
        "description": "Governance backlog requires operator attention before repair",
        "severity": "HIGH",
    },
    "INCREASE_REPAIR_THROUGHPUT": {
        "description": "System is stable — safe to increase repair wave cadence",
        "severity": "LOW",
    },
    "REVIEW_FAILED_CAMPAIGNS": {
        "description": "Review and redesign failed campaign patterns",
        "severity": "MEDIUM",
    },
}

# ---------------------------------------------------------------------------
# Signal weights for mode classification
# ---------------------------------------------------------------------------

# Thresholds for mode derivation
MODE_THRESHOLDS = {
    "governance_risk_score": 40,       # stability score below this = GOVERNANCE_RISK territory
    "degraded_score": 60,              # stability score below this = DEGRADED
    "high_regression_count": 2,        # regressions >= this triggers conservative mode
    "high_intervention_burden": 3,     # operator interventions >= this = high burden
    "high_p1_count": 5,               # P1 findings >= this = repair-focused mode needed
    "campaign_failure_threshold": 0.5, # failure rate above this = risky
    "good_effectiveness_score": 70,    # avg effectiveness above this = reuse candidate
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def classify_operating_mode(score_inputs: dict[str, Any]) -> str:
    """Derive runtime operating mode from signal inputs.

    Inputs (all optional, defaults to safe values):
      stability_score: int (0–100)
      stability_classification: str
      regression_count: int
      operator_intervention_count: int
      p1_finding_count: int
      campaign_failure_rate: float (0.0–1.0)
      avg_campaign_effectiveness: float (0–100)
      active_regressions: int
      high_risk_patterns: int
      abort_prone_count: int
    """
    t = MODE_THRESHOLDS
    stability_score    = int(score_inputs.get("stability_score", 100))
    stability_cls      = str(score_inputs.get("stability_classification", "STABLE")).upper()
    regression_count   = int(score_inputs.get("regression_count", 0))
    active_regressions = int(score_inputs.get("active_regressions", 0))
    interventions      = int(score_inputs.get("operator_intervention_count", 0))
    p1_count           = int(score_inputs.get("p1_finding_count", 0))
    failure_rate       = float(score_inputs.get("campaign_failure_rate", 0.0))
    avg_effectiveness  = float(score_inputs.get("avg_campaign_effectiveness", 0.0))
    high_risk_patterns = int(score_inputs.get("high_risk_patterns", 0))
    abort_prone_count  = int(score_inputs.get("abort_prone_count", 0))

    # Priority order: worst states first
    if stability_cls in ("GOVERNANCE_RISK",) or stability_score <= t["governance_risk_score"]:
        return "STABILIZE"

    if active_regressions >= t["high_regression_count"] or (
        high_risk_patterns >= 1 and abort_prone_count >= 1
    ):
        return "HIGH_RISK_HOLD"

    if stability_cls == "UNSTABLE" or (
        regression_count >= t["high_regression_count"] and interventions >= t["high_intervention_burden"]
    ):
        return "GOVERNANCE_REVIEW"

    if stability_cls == "DEGRADED" or failure_rate >= t["campaign_failure_threshold"]:
        return "CONSERVATIVE"

    if stability_score < t["degraded_score"]:
        return "THROUGHPUT_LIMITED"

    if avg_effectiveness >= t["good_effectiveness_score"] and regression_count == 0:
        return "PATTERN_REUSE_CANDIDATE"

    if p1_count >= t["high_p1_count"] or stability_cls in ("STABLE", "STABLE_WITH_RECURRING_DRIFT"):
        return "REPAIR_FOCUSED"

    return "CONSERVATIVE"


def recommendation_priority(recommendation: str) -> int:
    """Return sort priority for a recommendation (lower = more urgent)."""
    severity_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    entry = STRATEGY_RECOMMENDATIONS.get(recommendation, {})
    sev = str(entry.get("severity", "LOW")).upper()
    return severity_order.get(sev, 99)
