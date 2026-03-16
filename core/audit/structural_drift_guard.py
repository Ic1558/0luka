"""AG-36: Structural Drift Guard.

Detects recurring drift patterns across AG-31 finding history that indicate
structural instability rather than isolated mismatch.

Invariants:
  - read-only: never modifies codebase, findings, or governance state
  - emits pattern records and prevention suggestions only
  - no auto-correction of detected patterns

Runtime output:
  $LUKA_RUNTIME_ROOT/state/structural_drift_patterns.jsonl — append-only

Public API:
  detect_and_store_patterns(runtime_root=None) -> list[dict]
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str | None = None) -> Path:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed).")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Pattern taxonomy
# ---------------------------------------------------------------------------

# Maps (drift_type or drift_class) → pattern_class
_PATTERN_CLASS_MAP: dict[str, str] = {
    "naming_drift":             "recurring_naming_drift",
    "naming_drift_only":        "recurring_naming_drift",
    "api_surface_drift":        "recurring_route_surface_drift",
    "API_exposed_but_not_in_diagram": "recurring_route_surface_drift",
    "baseline_mismatch":        "recurring_baseline_mismatch",
    "operator_gate_regression": "recurring_operator_gate_regression",
    "operator_gate_missing":    "recurring_operator_gate_regression",
    "runtime_state_missing":    "recurring_state_file_absence",
    "state_file_expected_but_not_produced": "recurring_state_file_absence",
    "legacy_path_overlap":      "recurring_legacy_overlap",
    "legacy_component_still_active": "recurring_legacy_overlap",
    "wiring_gap":               "recurring_baseline_mismatch",
    "exists_but_not_wired":     "recurring_baseline_mismatch",
    "active_but_not_canonical": "recurring_baseline_mismatch",
}

# Severity by pattern count
def _severity_for_count(count: int) -> str:
    if count >= 5:
        return "HIGH"
    if count >= 3:
        return "MEDIUM"
    return "LOW"

# Prevention suggestions per pattern class
_PREVENTION_SUGGESTIONS: dict[str, list[str]] = {
    "recurring_naming_drift": [
        "mark alias explicitly in audit_baseline.py KNOWN_ACCEPTED_DRIFT",
        "update architecture diagram to use actual module name",
        "add naming convention test to regression suite",
    ],
    "recurring_route_surface_drift": [
        "align route naming with canonical API surface documentation",
        "add route surface verification to CI",
        "update mission_control_surface_verification.md",
    ],
    "recurring_baseline_mismatch": [
        "review wiring at canonical importer (task_dispatcher / router / executor)",
        "add integration test verifying the import chain",
        "update runtime capability matrix",
    ],
    "recurring_operator_gate_regression": [
        "add operator gate regression test to test suite",
        "add gate enforcement check to CI pipeline",
        "review all write endpoints for operator_id pattern",
    ],
    "recurring_state_file_absence": [
        "document state file as FIRST_RUN_OPTIONAL in audit_baseline.py",
        "ensure producer component is wired in runtime",
        "add state file presence check to health probe",
    ],
    "recurring_legacy_overlap": [
        "add deprecation notice to legacy module",
        "route all callers to canonical AG-20+ path",
        "schedule retirement task for legacy module",
    ],
}


# ---------------------------------------------------------------------------
# Source reader
# ---------------------------------------------------------------------------

def load_recent_findings(runtime_root: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    """Load recent AG-31 drift findings from drift_findings.jsonl."""
    try:
        findings_path = _state_dir(runtime_root) / "drift_findings.jsonl"
        if not findings_path.exists():
            return []
        lines = findings_path.read_text(encoding="utf-8").strip().splitlines()
        results = []
        for line in lines[-limit:]:
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def detect_recurring_drift_patterns(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect recurring drift patterns from a list of findings.

    Groups findings by pattern_class. A pattern is 'recurring' when it
    appears 2+ times across distinct components.

    Returns a list of pattern dicts.
    """
    # Count occurrences by pattern_class + component
    class_components: dict[str, list[str]] = {}

    for finding in findings:
        drift_type = str(finding.get("drift_type") or finding.get("drift_class") or "unknown")
        pattern_class = _PATTERN_CLASS_MAP.get(drift_type, "")
        if not pattern_class:
            continue
        component = str(finding.get("component") or finding.get("id") or "unknown")
        class_components.setdefault(pattern_class, []).append(component)

    patterns = []
    for pattern_class, components in class_components.items():
        count = len(components)
        if count < 2:
            continue  # not recurring — single occurrence only
        unique_components = list(dict.fromkeys(components))  # preserve order, deduplicate
        severity = _severity_for_count(count)
        patterns.append({
            "pattern_id": "pattern-" + uuid.uuid4().hex[:6],
            "pattern_class": pattern_class,
            "affected_components": unique_components,
            "count": count,
            "severity": severity,
            "ts": _now(),
        })

    return patterns


def classify_structural_drift(pattern: dict[str, Any]) -> dict[str, Any]:
    """Classify a detected drift pattern and attach prevention suggestions.

    Returns the pattern dict enriched with:
      - prevention_suggestions
      - structural_risk
    """
    pattern_class = str(pattern.get("pattern_class") or "")
    count = int(pattern.get("count") or 0)
    severity = pattern.get("severity") or _severity_for_count(count)

    prevention_suggestions = _PREVENTION_SUGGESTIONS.get(pattern_class, [
        "investigate recurring drift pattern manually",
        "document pattern in architecture review",
    ])

    structural_risk = "HIGH" if severity == "HIGH" else ("MEDIUM" if severity == "MEDIUM" else "LOW")

    return {
        **pattern,
        "prevention_suggestions": prevention_suggestions,
        "structural_risk": structural_risk,
        "operator_action_required": True,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_drift_patterns(patterns: list[dict[str, Any]], runtime_root: str | None = None) -> None:
    """Append detected structural drift patterns to structural_drift_patterns.jsonl."""
    if not patterns:
        return
    patterns_path = _state_dir(runtime_root) / "structural_drift_patterns.jsonl"
    with patterns_path.open("a", encoding="utf-8") as fh:
        for pattern in patterns:
            fh.write(json.dumps(pattern) + "\n")


def list_all_patterns(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all stored structural drift patterns."""
    try:
        patterns_path = _state_dir(runtime_root) / "structural_drift_patterns.jsonl"
        if not patterns_path.exists():
            return []
        results = []
        for line in patterns_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def detect_and_store_patterns(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Detect recurring structural drift patterns and store them.

    Steps:
      1. Load recent AG-31 findings
      2. Detect recurring patterns (2+ occurrences of same pattern_class)
      3. Classify each pattern + attach prevention suggestions
      4. Append to structural_drift_patterns.jsonl
      5. Return classified patterns

    Never modifies codebase, findings, or governance state.
    """
    findings = load_recent_findings(runtime_root)
    raw_patterns = detect_recurring_drift_patterns(findings)
    classified = [classify_structural_drift(p) for p in raw_patterns]
    store_drift_patterns(classified, runtime_root)
    return classified
