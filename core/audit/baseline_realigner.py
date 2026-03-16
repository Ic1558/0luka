"""AG-36: Baseline Realignment Engine.

Reads reconciled/accepted drift findings, evaluates eligibility for baseline
promotion, and generates deterministic baseline realignment proposals.

Invariants:
  - proposal-only: never modifies audit_baseline.py or canonical docs
  - never changes finding status (AG-32 owns lifecycle)
  - never executes repair (AG-34 owns execution)
  - every proposal has operator_action_required = True
  - every proposal starts with status = PROPOSED

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/baseline_realign_proposals.jsonl  — append-only
  $LUKA_RUNTIME_ROOT/state/baseline_realign_latest.json      — atomic overwrite

Public API:
  run_baseline_realignment(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
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
# Proposal type taxonomy
# ---------------------------------------------------------------------------

PROPOSAL_TYPE_MAP: dict[str, str] = {
    "naming_drift":             "mark_structural_alias",
    "baseline_mismatch":        "update_audit_baseline",
    "diagram_mismatch":         "update_architecture_diagram",
    "documentation_drift":      "update_sot_docs",
    "wiring_gap":               "update_runtime_capability_matrix",
    "api_surface_drift":        "update_architecture_diagram",
    "runtime_state_missing":    "update_runtime_capability_matrix",
    "legacy_path_overlap":      "update_audit_baseline",
    "missing_component":        "update_audit_baseline",
    "operator_gate_regression": "update_audit_baseline",
    "unknown":                  "update_sot_docs",
}

TARGET_ARTIFACTS_MAP: dict[str, list[str]] = {
    "update_audit_baseline":          ["core/audit/audit_baseline.py"],
    "update_architecture_diagram":    ["g/reports/architecture/0luka_architecture_diagram_ag30.md"],
    "update_runtime_capability_matrix": ["g/reports/architecture/0luka_runtime_capability_matrix.md"],
    "update_sot_docs":                ["g/reports/architecture/0luka_architecture_diagram_ag30.md",
                                       "g/reports/architecture/0luka_runtime_capability_matrix.md"],
    "mark_structural_alias":          ["core/audit/audit_baseline.py"],
}

_CONFIDENCE_BY_PROPOSAL_TYPE: dict[str, float] = {
    "mark_structural_alias":          0.93,
    "update_audit_baseline":          0.88,
    "update_architecture_diagram":    0.82,
    "update_runtime_capability_matrix": 0.80,
    "update_sot_docs":                0.72,
}


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

def list_reconciled_findings(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return findings eligible for baseline realignment consideration.

    Criteria (all must be true):
      - governance status is ACCEPTED or RESOLVED in AG-32
      - AG-35 reconciliation evidence attached (reconciliation_id present)
        OR finding was accepted by operator explicitly
      - not dismissed
      - not still OPEN or ESCALATED
      - not already baseline-promoted (no existing COMPLETED proposal for same finding)
    """
    state_d = _state_dir(runtime_root)

    # Load AG-32 governance status
    status_path = state_d / "drift_finding_status.json"
    if not status_path.exists():
        return []
    try:
        status_map: dict[str, dict[str, Any]] = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    eligible_ids = {
        fid for fid, rec in status_map.items()
        if rec.get("status") in ("ACCEPTED", "RESOLVED")
    }
    if not eligible_ids:
        return []

    # Load any existing baseline proposals to exclude already-promoted findings
    already_promoted: set[str] = set()
    proposals_path = state_d / "baseline_realign_proposals.jsonl"
    if proposals_path.exists():
        try:
            for line in proposals_path.read_text(encoding="utf-8").strip().splitlines():
                try:
                    p = json.loads(line)
                    if p.get("status") == "COMPLETED":
                        already_promoted.add(str(p.get("finding_id") or ""))
                except Exception:
                    pass
        except Exception:
            pass

    # Enrich with drift evidence from AG-31
    evidence_map: dict[str, dict[str, Any]] = {}
    findings_path = state_d / "drift_findings.jsonl"
    if findings_path.exists():
        try:
            for line in findings_path.read_text(encoding="utf-8").strip().splitlines():
                try:
                    rec = json.loads(line)
                    fid = str(rec.get("id") or rec.get("finding_id") or "")
                    if fid in eligible_ids:
                        evidence_map[fid] = rec
                except Exception:
                    pass
        except Exception:
            pass

    # Enrich with AG-35 reconciliation evidence
    recon_map: dict[str, dict[str, Any]] = {}
    recon_path = state_d / "repair_reconciliation_log.jsonl"
    if recon_path.exists():
        try:
            for line in recon_path.read_text(encoding="utf-8").strip().splitlines():
                try:
                    rec = json.loads(line)
                    fid = str(rec.get("finding_id") or "")
                    if fid in eligible_ids:
                        recon_map[fid] = rec
                except Exception:
                    pass
        except Exception:
            pass

    results = []
    for fid in eligible_ids:
        if fid in already_promoted:
            continue
        gov_rec = dict(status_map[fid])
        merged: dict[str, Any] = {}
        if fid in evidence_map:
            merged.update(evidence_map[fid])
        merged.update(gov_rec)
        merged["finding_id"] = fid
        if fid in recon_map:
            merged["reconciliation_id"] = recon_map[fid].get("reconciliation_id")
            merged["drift_state"] = recon_map[fid].get("drift_state")
            merged["governance_recommendation"] = recon_map[fid].get("governance_recommendation")
        results.append(merged)

    return results


# ---------------------------------------------------------------------------
# Eligibility evaluation
# ---------------------------------------------------------------------------

def evaluate_baseline_eligibility(finding: dict[str, Any]) -> dict[str, Any]:
    """Evaluate whether a finding is eligible for baseline proposal generation.

    Returns:
      {
        "eligible": bool,
        "reason": str,
        "confidence": float
      }
    """
    fid = str(finding.get("finding_id") or finding.get("id") or "unknown")
    status = str(finding.get("status") or "")
    drift_type = str(finding.get("drift_type") or finding.get("drift_class") or "unknown")

    # Must be ACCEPTED or RESOLVED
    if status not in ("ACCEPTED", "RESOLVED"):
        return {"eligible": False, "reason": f"status is {status!r}, must be ACCEPTED or RESOLVED", "confidence": 0.0}

    # Must not be a governance violation (operator gate regression)
    if drift_type == "operator_gate_regression":
        return {"eligible": False, "reason": "operator_gate_regression is not eligible for baseline promotion", "confidence": 0.0}

    # Confidence based on evidence quality
    has_reconciliation = bool(finding.get("reconciliation_id"))
    has_evidence = bool(finding.get("evidence") or finding.get("note") or finding.get("drift_state"))
    drift_state = str(finding.get("drift_state") or "")
    governance_rec = str(finding.get("governance_recommendation") or "")

    # Inconclusive reconciliation without explicit acceptance is not eligible
    if drift_state == "DRIFT_INCONCLUSIVE" and status != "ACCEPTED":
        return {"eligible": False, "reason": "drift state INCONCLUSIVE and not explicitly accepted by operator", "confidence": 0.0}

    # Eligible
    confidence = 0.70
    reason = "reconciled_and_accepted"

    if has_reconciliation:
        confidence += 0.12
        reason = "reconciled_and_repeat_confirmed"

    if drift_state in ("DRIFT_CLEARED", ""):
        confidence += 0.05

    if governance_rec == "recommend_RESOLVED":
        confidence += 0.06

    if not has_evidence:
        confidence -= 0.10
        reason = "accepted_without_reconciliation_evidence"

    confidence = round(min(confidence, 1.0), 2)

    return {"eligible": True, "reason": reason, "confidence": confidence}


# ---------------------------------------------------------------------------
# Proposal generation
# ---------------------------------------------------------------------------

def generate_baseline_proposal(finding: dict[str, Any]) -> dict[str, Any]:
    """Generate a deterministic baseline realignment proposal for an eligible finding.

    Does NOT write to disk — call store_baseline_proposal() for that.
    """
    eligibility = evaluate_baseline_eligibility(finding)
    if not eligibility["eligible"]:
        raise ValueError(f"finding {finding.get('finding_id')!r} is not eligible: {eligibility['reason']}")

    drift_type = str(finding.get("drift_type") or finding.get("drift_class") or "unknown")
    # Normalize AG-31 drift_class to drift_type if needed
    if drift_type in ("expected_by_SOT_but_missing", "canonical_component_but_no_runtime_evidence"):
        drift_type = "missing_component"
    elif drift_type in ("exists_but_not_wired", "active_but_not_canonical"):
        drift_type = "wiring_gap"
    elif drift_type == "naming_drift_only":
        drift_type = "naming_drift"

    proposal_type = PROPOSAL_TYPE_MAP.get(drift_type, "update_sot_docs")
    target_artifacts = TARGET_ARTIFACTS_MAP.get(proposal_type, [])
    confidence = eligibility["confidence"]

    return {
        "ts": _now(),
        "proposal_id": "prop-" + uuid.uuid4().hex[:8],
        "finding_id": str(finding.get("finding_id") or finding.get("id") or "unknown"),
        "reconciliation_id": str(finding.get("reconciliation_id") or ""),
        "proposal_type": proposal_type,
        "drift_type": drift_type,
        "target_artifacts": list(target_artifacts),
        "rationale": f"Finding accepted/resolved after governance review. Drift type: {drift_type}. Proposal: {proposal_type}.",
        "evidence_refs": [
            "drift_findings.jsonl",
            "drift_finding_status.json",
            "repair_reconciliation_log.jsonl",
        ],
        "operator_action_required": True,   # always True
        "status": "PROPOSED",
        "confidence": confidence,
        "eligibility_reason": eligibility["reason"],
        "source_note": str(finding.get("note") or ""),
        "governance_recommendation": str(finding.get("governance_recommendation") or ""),
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_baseline_proposal(proposal: dict[str, Any], runtime_root: str | None = None) -> None:
    """Append a baseline realignment proposal to baseline_realign_proposals.jsonl."""
    proposals_path = _state_dir(runtime_root) / "baseline_realign_proposals.jsonl"
    with proposals_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(proposal) + "\n")


def _write_realign_latest(summary: dict[str, Any], runtime_root: str | None = None) -> None:
    """Atomically overwrite baseline_realign_latest.json."""
    state_d = _state_dir(runtime_root)
    path = state_d / "baseline_realign_latest.json"
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


def list_all_proposals(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all stored baseline realignment proposals."""
    try:
        proposals_path = _state_dir(runtime_root) / "baseline_realign_proposals.jsonl"
        if not proposals_path.exists():
            return []
        results = []
        for line in proposals_path.read_text(encoding="utf-8").strip().splitlines():
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

def run_baseline_realignment(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-36 baseline realignment flow.

    Steps:
      1. list reconciled/accepted findings
      2. evaluate eligibility
      3. generate proposals for eligible findings
      4. store proposals (append-only)
      5. write latest summary (atomic)
      6. return summary

    Invariants:
      - never modifies audit_baseline.py
      - never modifies canonical architecture docs
      - never changes finding status
      - only writes to baseline_realign_proposals.jsonl + baseline_realign_latest.json
    """
    findings = list_reconciled_findings(runtime_root)
    proposals: list[dict[str, Any]] = []
    skipped: list[str] = []
    errors: list[str] = []

    for finding in findings:
        fid = str(finding.get("finding_id") or "unknown")
        try:
            eligibility = evaluate_baseline_eligibility(finding)
            if not eligibility["eligible"]:
                skipped.append(f"{fid}: {eligibility['reason']}")
                continue
            proposal = generate_baseline_proposal(finding)
            store_baseline_proposal(proposal, runtime_root)
            proposals.append(proposal)
        except Exception as exc:
            errors.append(f"{fid}: {exc}")

    summary: dict[str, Any] = {
        "ts": _now(),
        "findings_evaluated": len(findings),
        "proposals_generated": len(proposals),
        "skipped": skipped,
        "errors": errors,
        "proposals": proposals,
    }

    try:
        _write_realign_latest(summary, runtime_root)
    except Exception as exc:
        summary["errors"].append(f"latest write: {exc}")

    return summary
