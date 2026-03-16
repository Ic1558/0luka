"""AG-41: Campaign Pattern Registry.

Canonical campaign pattern class definitions and normalization logic.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Campaign outcome classes
# ---------------------------------------------------------------------------

CAMPAIGN_OUTCOME_CLASSES: dict[str, str] = {
    "CAMPAIGN_SUCCESS":      "all targeted findings resolved, no regression detected",
    "CAMPAIGN_PARTIAL":      "majority resolved, some findings remain or inconclusive",
    "CAMPAIGN_FAILED":       "repair execution failed or most findings unresolved",
    "CAMPAIGN_REGRESSION":   "post-campaign drift increased or new findings emerged",
    "CAMPAIGN_INCONCLUSIVE": "insufficient evidence to determine campaign outcome",
}

# ---------------------------------------------------------------------------
# Campaign recommendation classes
# ---------------------------------------------------------------------------

CAMPAIGN_RECOMMENDATION_CLASSES: dict[str, str] = {
    "CONTINUE_PATTERN":  "campaign pattern is effective — reuse recommended",
    "REVIEW_PATTERN":    "pattern has mixed results — operator review before reuse",
    "RETIRE_PATTERN":    "pattern consistently underperforms — avoid reuse",
    "HIGH_RISK_PATTERN": "pattern associated with regressions — operator approval required",
}

# ---------------------------------------------------------------------------
# Campaign pattern classes (structural analysis)
# ---------------------------------------------------------------------------

CAMPAIGN_PATTERN_CLASSES: dict[str, dict[str, Any]] = {
    "repeatable_success_pattern": {
        "description": "campaign consistently resolves targeted findings without regression",
        "signals": ["high_success_rate", "low_regression_count", "low_intervention_count"],
        "recommendation": "CONTINUE_PATTERN",
    },
    "high_intervention_pattern": {
        "description": "campaign requires frequent operator intervention to complete",
        "signals": ["high_intervention_count", "frequent_wave_pauses"],
        "recommendation": "REVIEW_PATTERN",
    },
    "regression_prone_pattern": {
        "description": "campaign execution correlates with post-campaign drift regression",
        "signals": ["regression_after_campaign", "new_findings_post_campaign"],
        "recommendation": "HIGH_RISK_PATTERN",
    },
    "overlap_sensitive_pattern": {
        "description": "campaign touches overlapping components causing instability",
        "signals": ["target_overlap_conflicts", "multi_wave_same_component"],
        "recommendation": "REVIEW_PATTERN",
    },
    "pause_heavy_pattern": {
        "description": "campaign frequently paused before completion",
        "signals": ["high_pause_frequency", "incomplete_wave_ratio"],
        "recommendation": "REVIEW_PATTERN",
    },
    "abort_prone_pattern": {
        "description": "campaign frequently aborted due to scope or safety blocks",
        "signals": ["high_abort_count", "scope_block_frequency"],
        "recommendation": "RETIRE_PATTERN",
    },
    "low_yield_pattern": {
        "description": "campaign resolves few findings relative to effort",
        "signals": ["low_success_rate", "high_wave_count", "low_resolution_ratio"],
        "recommendation": "REVIEW_PATTERN",
    },
}


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------

def is_valid_outcome_class(name: str) -> bool:
    return name in CAMPAIGN_OUTCOME_CLASSES


def is_valid_pattern_class(name: str) -> bool:
    return name in CAMPAIGN_PATTERN_CLASSES


def recommendation_for_pattern(pattern_class: str) -> str:
    """Return the default recommendation class for a pattern class."""
    entry = CAMPAIGN_PATTERN_CLASSES.get(pattern_class, {})
    return entry.get("recommendation", "REVIEW_PATTERN")


def classify_campaign_patterns(metrics: dict[str, Any]) -> list[str]:
    """Return list of applicable pattern classes given campaign metrics.

    Applies heuristic signal matching — deterministic given the same metrics.
    """
    patterns: list[str] = []

    success_rate    = float(metrics.get("repair_success_rate", 0.0))
    recon_rate      = float(metrics.get("reconciliation_pass_ratio", 0.0))
    regression_count = int(metrics.get("regression_count", 0))
    intervention_ct  = int(metrics.get("operator_intervention_count", 0))
    pause_count      = int(metrics.get("wave_pause_count", 0))
    abort_count      = int(metrics.get("wave_abort_count", 0))
    wave_count       = int(metrics.get("total_waves", 0))
    resolved_count   = int(metrics.get("findings_resolved", 0))
    total_targeted   = int(metrics.get("findings_targeted", 1))

    # Repeatable success
    if success_rate >= 0.85 and regression_count == 0 and intervention_ct <= 1:
        patterns.append("repeatable_success_pattern")

    # Regression prone
    if regression_count >= 2:
        patterns.append("regression_prone_pattern")

    # High intervention
    if intervention_ct >= 3:
        patterns.append("high_intervention_pattern")

    # Pause heavy
    if wave_count > 0 and pause_count / max(wave_count, 1) >= 0.5:
        patterns.append("pause_heavy_pattern")

    # Abort prone
    if abort_count >= 2:
        patterns.append("abort_prone_pattern")

    # Low yield
    if total_targeted > 0 and resolved_count / max(total_targeted, 1) < 0.4 and wave_count >= 3:
        patterns.append("low_yield_pattern")

    return patterns
