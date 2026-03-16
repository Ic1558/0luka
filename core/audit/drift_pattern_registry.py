"""AG-37: Drift Pattern Registry.

Canonical enumeration of recurring drift pattern classes with severity,
description, and mapping from AG-31 drift_class/drift_type source values.

This module is pure data — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Pattern class registry
# ---------------------------------------------------------------------------

PATTERN_CLASSES: dict[str, dict[str, Any]] = {
    "recurring_naming_drift": {
        "description": "Component or module appears under a different name than declared in SOT/architecture",
        "default_severity": "LOW",
        "source_drift_types": ("naming_drift", "naming_drift_only"),
        "prevention_hint": "mark alias in audit_baseline.py KNOWN_ACCEPTED_DRIFT",
    },
    "recurring_route_surface_drift": {
        "description": "API routes exposed but not reflected in canonical architecture diagram",
        "default_severity": "MEDIUM",
        "source_drift_types": ("api_surface_drift", "API_exposed_but_not_in_diagram"),
        "prevention_hint": "update mission_control_surface_verification.md and architecture diagram",
    },
    "recurring_operator_gate_regression": {
        "description": "Write endpoint missing operator_id enforcement — governance boundary weakening",
        "default_severity": "CRITICAL",
        "source_drift_types": ("operator_gate_regression", "operator_gate_missing"),
        "prevention_hint": "add operator gate regression test to CI; enforce gate check in code review",
    },
    "recurring_state_file_absence": {
        "description": "Expected runtime state file not produced on first or subsequent runs",
        "default_severity": "MEDIUM",
        "source_drift_types": ("runtime_state_missing", "state_file_expected_but_not_produced"),
        "prevention_hint": "document as FIRST_RUN_OPTIONAL in audit_baseline.py or fix producer wiring",
    },
    "recurring_legacy_overlap": {
        "description": "Legacy component still active alongside canonical replacement",
        "default_severity": "MEDIUM",
        "source_drift_types": ("legacy_path_overlap", "legacy_component_still_active"),
        "prevention_hint": "add deprecation notice; route callers to canonical path; schedule retirement",
    },
    "recurring_failed_repair_cycle": {
        "description": "Repair plans generated but execution consistently fails or is never approved",
        "default_severity": "HIGH",
        "source_drift_types": (),  # derived from repair_execution records
        "prevention_hint": "review target_files scope and approved_action_scope; simplify repair plan",
    },
    "recurring_baseline_mismatch": {
        "description": "Component wired incorrectly or not imported by canonical importer across multiple runs",
        "default_severity": "MEDIUM",
        "source_drift_types": ("wiring_gap", "exists_but_not_wired", "active_but_not_canonical",
                               "baseline_mismatch"),
        "prevention_hint": "update runtime capability matrix; add wiring integration test",
    },
    "recurring_reconciliation_failure": {
        "description": "Reconciliation consistently returns FAILED or INCONCLUSIVE for the same component",
        "default_severity": "HIGH",
        "source_drift_types": (),  # derived from reconciliation records
        "prevention_hint": "investigate root cause of repeated reconciliation failure; escalate to operator",
    },
}

# ---------------------------------------------------------------------------
# Severity ordering (for sorting/comparison)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH":     3,
    "MEDIUM":   2,
    "LOW":      1,
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_valid_pattern_class(name: str) -> bool:
    """Return True if name is a known pattern class."""
    return name in PATTERN_CLASSES


def default_pattern_severity(name: str) -> str:
    """Return the default severity for a pattern class, or 'MEDIUM' if unknown."""
    entry = PATTERN_CLASSES.get(name)
    if entry is None:
        return "MEDIUM"
    return str(entry.get("default_severity", "MEDIUM"))


def severity_value(severity: str) -> int:
    """Return numeric severity value for comparison (higher = more severe)."""
    return _SEVERITY_ORDER.get(severity.upper(), 0)


def all_pattern_class_names() -> list[str]:
    """Return all registered pattern class names."""
    return list(PATTERN_CLASSES.keys())


def pattern_source_types(name: str) -> tuple[str, ...]:
    """Return source drift_types that map to this pattern class."""
    entry = PATTERN_CLASSES.get(name, {})
    return tuple(entry.get("source_drift_types", ()))


def classify_drift_to_pattern(drift_type: str) -> str | None:
    """Map a drift_type or drift_class string to a pattern class name, or None."""
    for cls_name, entry in PATTERN_CLASSES.items():
        if drift_type in entry.get("source_drift_types", ()):
            return cls_name
    return None
