"""AG-33: Drift Repair Planning Engine.

Reads AG-32 ESCALATED findings, classifies drift type, and generates
deterministic repair plan artifacts for operator review.

Invariants:
  - planning-only: never modifies codebase, finding status, or audit_baseline.py
  - reads AG-31 drift evidence + AG-32 governance state
  - writes only to drift_repair_plans.jsonl (append-only) and
    drift_repair_plan_latest.json (atomic overwrite)
  - every generated plan has operator_action_required = true
  - every plan starts with status = PROPOSED

Public API:
  run_repair_planning(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repair strategy taxonomy
# Maps drift_type → repair_strategy (deterministic)
# ---------------------------------------------------------------------------

STRATEGY_MAP: dict[str, str] = {
    "missing_component":        "create_missing_component",
    "wiring_gap":               "wire_component_into_runtime_path",
    "api_surface_drift":        "align_api_surface",
    "operator_gate_regression": "restore_operator_guard",
    "runtime_state_missing":    "restore_state_producer",
    "naming_drift":             "rename_or_document_alias",
    "baseline_mismatch":        "update_baseline_proposal",
    "legacy_path_overlap":      "retire_or_isolate_legacy_path",
    "diagram_mismatch":         "update_architecture_docs",
    "documentation_drift":      "update_sot_docs",
    "unknown":                  "investigate_and_document",
}

# Maps AG-31 drift_class → drift_type
DRIFT_CLASS_TO_TYPE: dict[str, str] = {
    "expected_by_SOT_but_missing":              "missing_component",
    "exists_but_not_wired":                     "wiring_gap",
    "active_but_not_canonical":                 "wiring_gap",
    "API_exposed_but_not_in_diagram":           "api_surface_drift",
    "canonical_component_but_no_runtime_evidence": "runtime_state_missing",
    "operator_gate_missing":                    "operator_gate_regression",
    "state_file_expected_but_not_produced":     "runtime_state_missing",
    "naming_drift_only":                        "naming_drift",
    "diagram_path_mismatch":                    "diagram_mismatch",
    "legacy_component_still_active":            "legacy_path_overlap",
    "unknown":                                  "documentation_drift",
}

# Confidence level per drift_type (0.0–1.0)
_CONFIDENCE_MAP: dict[str, float] = {
    "operator_gate_regression": 0.97,
    "missing_component":        0.92,
    "wiring_gap":               0.88,
    "runtime_state_missing":    0.85,
    "legacy_path_overlap":      0.80,
    "api_surface_drift":        0.78,
    "naming_drift":             0.75,
    "baseline_mismatch":        0.72,
    "diagram_mismatch":         0.65,
    "documentation_drift":      0.55,
    "unknown":                  0.40,
}

# Proposed actions per repair_strategy
_ACTIONS_MAP: dict[str, list[str]] = {
    "create_missing_component": [
        "identify what functionality the missing component should provide",
        "create module at expected path",
        "add unit tests",
        "verify importability",
    ],
    "wire_component_into_runtime_path": [
        "identify the canonical importer (task_dispatcher / router / executor)",
        "add import statement at the canonical call site",
        "add integration test verifying the import chain",
        "re-run AG-31 audit to confirm wiring resolved",
    ],
    "align_api_surface": [
        "document extra route in architecture diagram",
        "or: remove undocumented route if no longer needed",
        "update mission_control_surface_verification.md",
    ],
    "restore_operator_guard": [
        "add operator_id check at the top of the handler",
        "return 403 if operator_id missing or empty",
        "add operator gate test to test suite",
        "re-run AG-31 audit to confirm gate present",
    ],
    "restore_state_producer": [
        "identify which component is responsible for producing the state file",
        "ensure component is active and wired in runtime",
        "trigger at least one run to produce initial state file",
        "verify state file path in LUKA_RUNTIME_ROOT/state/",
    ],
    "rename_or_document_alias": [
        "update SOT / architecture diagram to use actual module name",
        "or: add naming alias note to audit_baseline.py KNOWN_ACCEPTED_DRIFT",
        "update capability matrix to reflect actual name",
    ],
    "update_baseline_proposal": [
        "review accepted drift item",
        "add entry to KNOWN_ACCEPTED_DRIFT in core/audit/audit_baseline.py",
        "use promote_to_baseline API to create a formal proposal first",
    ],
    "retire_or_isolate_legacy_path": [
        "confirm legacy path is no longer needed",
        "add deprecation notice to legacy module",
        "route all callers to canonical AG-20+ path",
        "remove or archive legacy module after verification",
    ],
    "update_architecture_docs": [
        "update 0luka_architecture_diagram_ag30.md to reflect actual path",
        "update 0luka_runtime_capability_matrix.md",
        "re-run AG-31 audit to confirm drift resolved",
    ],
    "update_sot_docs": [
        "update canonical SOT document",
        "ensure all architecture truth layer artifacts are consistent",
    ],
    "investigate_and_document": [
        "investigate the finding manually",
        "classify drift type more precisely",
        "document findings and proposed fix",
    ],
}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str | None = None) -> Path:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

def list_escalated_findings(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all findings that currently have status ESCALATED in AG-32 governance.

    Enriches governance status records with drift details from
    drift_findings.jsonl (AG-31 output) where available.
    """
    state_d = _state_dir(runtime_root)

    # Load AG-32 status map
    status_path = state_d / "drift_finding_status.json"
    if not status_path.exists():
        return []
    try:
        status_map: dict[str, dict[str, Any]] = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    escalated_ids = {
        fid for fid, rec in status_map.items()
        if rec.get("status") == "ESCALATED"
    }
    if not escalated_ids:
        return []

    # Enrich with AG-31 drift evidence
    evidence: dict[str, dict[str, Any]] = {}
    findings_path = state_d / "drift_findings.jsonl"
    if findings_path.exists():
        try:
            for line in findings_path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    fid = str(rec.get("id") or rec.get("finding_id") or "")
                    if fid in escalated_ids:
                        evidence[fid] = rec
                except Exception:
                    pass
        except Exception:
            pass

    results = []
    for fid in escalated_ids:
        gov_rec = dict(status_map[fid])
        if fid in evidence:
            # Merge evidence into governance record (governance fields take precedence)
            merged = {**evidence[fid], **gov_rec}
        else:
            merged = gov_rec
        merged["finding_id"] = fid
        results.append(merged)

    return results


def _load_all_plans(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load all repair plans from drift_repair_plans.jsonl."""
    try:
        plans_path = _state_dir(runtime_root) / "drift_repair_plans.jsonl"
        if not plans_path.exists():
            return []
        results = []
        for line in plans_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_drift_type(finding: dict[str, Any]) -> dict[str, Any]:
    """Classify a drift finding into a deterministic drift_type + repair_strategy.

    Uses the drift_class field (from AG-31) to determine type.
    Falls back to evidence/component text scanning if drift_class absent.
    """
    drift_class = str(finding.get("drift_class") or finding.get("class") or "unknown")
    drift_type = DRIFT_CLASS_TO_TYPE.get(drift_class, "unknown")

    # Refine using evidence/component text when drift_class is generic
    if drift_type in ("unknown", "documentation_drift"):
        component = str(finding.get("component") or "").lower()
        evidence = str(finding.get("evidence") or "").lower()
        combined = component + " " + evidence

        if "operator_id" in combined or "403" in combined or "gate" in combined:
            drift_type = "operator_gate_regression"
        elif "not found" in combined or "none" in combined or "missing" in combined:
            drift_type = "missing_component"
        elif "not wired" in combined or "not imported" in combined:
            drift_type = "wiring_gap"
        elif "state file" in combined or "jsonl" in combined:
            drift_type = "runtime_state_missing"
        elif "route" in combined or "api" in combined or "/api/" in combined:
            drift_type = "api_surface_drift"

    repair_strategy = STRATEGY_MAP.get(drift_type, "investigate_and_document")
    confidence = _CONFIDENCE_MAP.get(drift_type, 0.50)

    return {
        "drift_type": drift_type,
        "repair_strategy": repair_strategy,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Target file inference
# ---------------------------------------------------------------------------

def _infer_target_files(finding: dict[str, Any], drift_type: str) -> list[str]:
    """Infer relevant target files from finding evidence."""
    targets: list[str] = []
    component = str(finding.get("component") or "")
    evidence = str(finding.get("evidence") or "")

    # Module path → file path
    # e.g. "core.audit.something" → "core/audit/something.py"
    if "." in component and not component.startswith("/") and not component.startswith("GET ") and not component.startswith("POST "):
        # Strip trailing state file references like "→ something.jsonl"
        module_part = component.split("→")[0].strip().split(" ")[0].strip()
        if module_part and "." in module_part:
            # Check for known top-level packages
            file_path = module_part.replace(".", "/") + ".py"
            targets.append(file_path)

    # Route → API file + MCS
    if component.startswith(("GET ", "POST ", "PATCH ", "DELETE ", "PUT ")):
        route_path = component.split(" ", 1)[-1] if " " in component else ""
        # Infer api_*.py from route prefix
        segments = [s for s in route_path.split("/") if s and s != "api"]
        if segments:
            api_file = f"interface/operator/api_{segments[0]}.py"
            targets.append(api_file)
        targets.append("interface/operator/mission_control_server.py")

    # State file reference
    for ext in (".jsonl", ".json"):
        if ext in evidence or ext in component:
            # Extract filename
            parts = (evidence + " " + component).split()
            for part in parts:
                if ext in part:
                    fname = part.strip("'\".,()").split("/")[-1]
                    if fname.endswith(ext):
                        targets.append(f"$LUKA_RUNTIME_ROOT/state/{fname}")
                        break

    # Architecture docs for diagram/naming drift
    if drift_type in ("diagram_mismatch", "naming_drift", "documentation_drift"):
        targets.extend([
            "g/reports/architecture/0luka_architecture_diagram_ag30.md",
            "g/reports/architecture/0luka_runtime_capability_matrix.md",
        ])

    # Baseline for baseline drift
    if drift_type == "baseline_mismatch":
        targets.append("core/audit/audit_baseline.py")

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

def generate_repair_plan(finding: dict[str, Any]) -> dict[str, Any]:
    """Generate a deterministic repair plan artifact for an escalated finding.

    Returns a plan dict. Does NOT write to disk — call store_repair_plan() for that.
    """
    classification = classify_drift_type(finding)
    drift_type = classification["drift_type"]
    repair_strategy = classification["repair_strategy"]
    confidence = classification["confidence"]

    target_files = _infer_target_files(finding, drift_type)
    proposed_actions = _ACTIONS_MAP.get(repair_strategy, ["investigate_and_document"])

    severity = str(finding.get("severity") or "MEDIUM")
    drift_class = str(finding.get("drift_class") or "unknown")
    finding_id = str(finding.get("finding_id") or finding.get("id") or "unknown")

    return {
        "ts": _now(),
        "plan_id": uuid.uuid4().hex[:10],
        "finding_id": finding_id,
        "severity": severity,
        "drift_class": drift_class,
        "drift_type": drift_type,
        "repair_strategy": repair_strategy,
        "target_files": target_files,
        "proposed_actions": list(proposed_actions),
        "operator_action_required": True,   # always True — no auto-repair
        "status": "PROPOSED",
        "confidence": confidence,
        "source_finding_note": str(finding.get("note") or ""),
        "source_evidence": str(finding.get("evidence") or ""),
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_repair_plan(plan: dict[str, Any], runtime_root: str | None = None) -> None:
    """Append a repair plan to drift_repair_plans.jsonl (append-only)."""
    plans_path = _state_dir(runtime_root) / "drift_repair_plans.jsonl"
    with plans_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(plan) + "\n")


def _write_latest_summary(summary: dict[str, Any], runtime_root: str | None = None) -> None:
    """Atomically overwrite drift_repair_plan_latest.json."""
    state_d = _state_dir(runtime_root)
    path = state_d / "drift_repair_plan_latest.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_repair_planning(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-33 repair planning flow.

    Steps:
      1. list ESCALATED findings from AG-32 state
      2. classify drift type for each
      3. generate repair plan
      4. store plan (append-only)
      5. return summary

    Invariants:
      - never modifies codebase
      - never changes finding status
      - never modifies audit_baseline.py
      - only writes to drift_repair_plans.jsonl + drift_repair_plan_latest.json
    """
    escalated = list_escalated_findings(runtime_root)
    plans: list[dict[str, Any]] = []
    errors: list[str] = []

    for finding in escalated:
        try:
            plan = generate_repair_plan(finding)
            store_repair_plan(plan, runtime_root)
            plans.append(plan)
        except Exception as exc:
            errors.append(f"finding {finding.get('finding_id')}: {exc}")

    summary: dict[str, Any] = {
        "ts": _now(),
        "escalated_found": len(escalated),
        "plans_generated": len(plans),
        "errors": errors,
        "plans": plans,
    }

    try:
        _write_latest_summary(summary, runtime_root)
    except Exception as exc:
        summary["errors"].append(f"latest summary write: {exc}")

    return summary


def get_plans_for_finding(finding_id: str, runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all repair plans for a specific finding_id."""
    return [
        p for p in _load_all_plans(runtime_root)
        if p.get("finding_id") == finding_id
    ]


def list_all_plans(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all stored repair plans."""
    return _load_all_plans(runtime_root)
