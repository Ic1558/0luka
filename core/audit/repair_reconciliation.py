"""AG-35: Repair Verification & Governance Reconciliation Engine.

Consumes AG-34 execution records, verifies repair outcomes, and produces
governance recommendations for AG-32.

Invariants:
  - never modifies drift_finding_status.json (AG-32 owns finding lifecycle)
  - never modifies audit_baseline.py
  - never auto-closes findings
  - never auto-promotes baseline
  - produces recommendations only — operator applies them via AG-32 API
  - operator_action_required = True always

Drift states:
  DRIFT_CLEARED | DRIFT_PERSISTS | DRIFT_REGRESSED | DRIFT_INCONCLUSIVE

Governance recommendations:
  recommend_RESOLVED | recommend_ESCALATED_AGAIN | recommend_OPEN | recommend_HIGH_PRIORITY_ESCALATION

Public API:
  run_reconciliation(execution_id, operator_id, runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from core.audit.reconciliation_store import (
    append_reconciliation_log,
    new_reconciliation_id,
    save_reconciliation_latest,
)


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
# Execution record loader
# ---------------------------------------------------------------------------

def _load_execution_record(execution_id: str, runtime_root: str | None = None) -> dict[str, Any] | None:
    try:
        log_path = _state_dir(runtime_root) / "drift_repair_execution_log.jsonl"
        if not log_path.exists():
            return None
        for line in log_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                rec = json.loads(line)
                if rec.get("execution_id") == execution_id:
                    return rec
            except Exception:
                pass
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Verification: compare before/after state
# ---------------------------------------------------------------------------

def verify_execution_evidence(execution: dict[str, Any]) -> dict[str, Any]:
    """Verify repair execution by comparing before/after state snapshots.

    Returns:
      {
        "verification_status": "PASSED" | "FAILED" | "INCONCLUSIVE",
        "checks": [...],
        "reason": str
      }
    """
    checks = []
    failed = False
    inconclusive = False

    # Check 1: executed actions present
    executed_actions = execution.get("executed_actions", [])
    if not executed_actions:
        checks.append({"check": "executed_actions", "result": "FAILED", "detail": "no actions recorded"})
        failed = True
    else:
        checks.append({"check": "executed_actions", "result": "PASSED",
                       "detail": f"{len(executed_actions)} actions"})

    # Check 2: before_state captured
    before_state = execution.get("before_state", [])
    if not before_state:
        checks.append({"check": "before_state", "result": "INCONCLUSIVE", "detail": "no pre-repair snapshots"})
        inconclusive = True
    else:
        checks.append({"check": "before_state", "result": "PASSED",
                       "detail": f"{len(before_state)} file snapshots"})

    # Check 3: after_state captured
    after_state = execution.get("after_state", [])
    if not after_state:
        checks.append({"check": "after_state", "result": "INCONCLUSIVE", "detail": "no post-repair snapshots"})
        inconclusive = True
    else:
        checks.append({"check": "after_state", "result": "PASSED",
                       "detail": f"{len(after_state)} file snapshots"})

    # Check 4: scope was ALLOW (not BLOCK/ESCALATE)
    scope_verdict = execution.get("scope_verdict", "")
    if scope_verdict == "ALLOW":
        checks.append({"check": "scope_verdict", "result": "PASSED"})
    elif scope_verdict in ("BLOCK", "ESCALATE"):
        checks.append({"check": "scope_verdict", "result": "FAILED",
                       "detail": f"scope was {scope_verdict}"})
        failed = True
    else:
        checks.append({"check": "scope_verdict", "result": "INCONCLUSIVE",
                       "detail": "scope_verdict missing from record"})
        inconclusive = True

    # Check 5: execution status was EXECUTED
    exec_status = execution.get("status", "")
    if exec_status == "EXECUTED":
        checks.append({"check": "execution_status", "result": "PASSED"})
    elif exec_status == "FAILED":
        checks.append({"check": "execution_status", "result": "FAILED",
                       "detail": "execution status is FAILED"})
        failed = True
    else:
        checks.append({"check": "execution_status", "result": "INCONCLUSIVE",
                       "detail": f"execution status is {exec_status!r}"})
        inconclusive = True

    if failed:
        verification_status = "FAILED"
        reason = "one or more verification checks failed"
    elif inconclusive:
        verification_status = "INCONCLUSIVE"
        reason = "insufficient evidence to confirm repair outcome"
    else:
        verification_status = "PASSED"
        reason = "all verification checks passed"

    return {
        "verification_status": verification_status,
        "checks": checks,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Bounded drift re-check
# ---------------------------------------------------------------------------

def bounded_drift_recheck(execution: dict[str, Any], runtime_root: str | None = None) -> str:
    """Perform a bounded check to determine drift state after repair.

    Compares before/after sha256 for each target file.
    Does NOT run a full AG-31 scan.

    Returns: DRIFT_CLEARED | DRIFT_PERSISTS | DRIFT_REGRESSED | DRIFT_INCONCLUSIVE
    """
    before_state = execution.get("before_state", [])
    after_state = execution.get("after_state", [])

    if not before_state or not after_state:
        return "DRIFT_INCONCLUSIVE"

    # Build maps
    before_map = {s.get("path"): s for s in before_state}
    after_map = {s.get("path"): s for s in after_state}

    any_changed = False
    any_missing = False

    for path, before_snap in before_map.items():
        after_snap = after_map.get(path)
        if after_snap is None:
            any_missing = True
            continue
        hash_before = before_snap.get("sha256_before", "")
        hash_after = after_snap.get("sha256_after", "")
        if hash_before and hash_after and hash_before != hash_after:
            any_changed = True

    # No target files changed at all → repair may not have applied
    if not any_changed and not any_missing:
        # Execution model was dry_record (v1) — file hashes won't differ
        # Check if execution model is dry — treat as inconclusive not "persists"
        exec_model = execution.get("execution_model", "")
        if exec_model == "dry_record":
            return "DRIFT_INCONCLUSIVE"
        return "DRIFT_PERSISTS"

    if any_missing:
        return "DRIFT_REGRESSED"

    if any_changed:
        return "DRIFT_CLEARED"

    return "DRIFT_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Governance recommendation
# ---------------------------------------------------------------------------

_RECOMMENDATION_MAP: dict[tuple[str, str], str] = {
    ("DRIFT_CLEARED",       "PASSED"):       "recommend_RESOLVED",
    ("DRIFT_CLEARED",       "INCONCLUSIVE"): "recommend_OPEN",
    ("DRIFT_CLEARED",       "FAILED"):       "recommend_OPEN",
    ("DRIFT_PERSISTS",      "PASSED"):       "recommend_ESCALATED_AGAIN",
    ("DRIFT_PERSISTS",      "FAILED"):       "recommend_ESCALATED_AGAIN",
    ("DRIFT_PERSISTS",      "INCONCLUSIVE"): "recommend_ESCALATED_AGAIN",
    ("DRIFT_REGRESSED",     "PASSED"):       "recommend_HIGH_PRIORITY_ESCALATION",
    ("DRIFT_REGRESSED",     "FAILED"):       "recommend_HIGH_PRIORITY_ESCALATION",
    ("DRIFT_REGRESSED",     "INCONCLUSIVE"): "recommend_HIGH_PRIORITY_ESCALATION",
    ("DRIFT_INCONCLUSIVE",  "PASSED"):       "recommend_OPEN",
    ("DRIFT_INCONCLUSIVE",  "FAILED"):       "recommend_ESCALATED_AGAIN",
    ("DRIFT_INCONCLUSIVE",  "INCONCLUSIVE"): "recommend_OPEN",
}


def compute_governance_recommendation(drift_state: str, verification_status: str) -> str:
    """Return the governance recommendation for the given drift state + verification status."""
    return _RECOMMENDATION_MAP.get(
        (drift_state, verification_status),
        "recommend_OPEN",
    )


# ---------------------------------------------------------------------------
# End-to-end reconciliation orchestrator
# ---------------------------------------------------------------------------

def run_reconciliation(
    execution_id: str,
    operator_id: str,
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Run AG-35 reconciliation for the given execution_id.

    Steps:
      1. Load AG-34 execution record
      2. Verify execution evidence (before/after state, actions, scope)
      3. Run bounded drift re-check
      4. Compute governance recommendation
      5. Write reconciliation record (append-only)
      6. Write latest summary (atomic)
      7. Return result

    Does NOT modify drift_finding_status.json.
    Does NOT modify audit_baseline.py.
    Does NOT close findings.
    operator_action_required = True always.
    """
    reconciliation_id = new_reconciliation_id()
    ts_start = _now()

    # Step 1: Load execution record
    execution = _load_execution_record(execution_id, runtime_root)
    if execution is None:
        return {
            "ok": False,
            "reconciliation_id": reconciliation_id,
            "reason": f"execution_id {execution_id!r} not found",
            "status": "FAILED",
        }

    finding_id = str(execution.get("finding_id") or "")

    # Step 2: Verify evidence
    verification = verify_execution_evidence(execution)
    verification_status = verification["verification_status"]

    # Step 3: Bounded drift re-check
    drift_state = bounded_drift_recheck(execution, runtime_root)

    # Step 4: Governance recommendation
    recommendation = compute_governance_recommendation(drift_state, verification_status)

    # Step 5: Build reconciliation record
    record: dict[str, Any] = {
        "ts": ts_start,
        "reconciliation_id": reconciliation_id,
        "execution_id": execution_id,
        "finding_id": finding_id,
        "operator_id": operator_id,
        "verification_status": verification_status,
        "verification_checks": verification["checks"],
        "drift_state": drift_state,
        "governance_recommendation": recommendation,
        "evidence_refs": [
            "drift_repair_execution_log.jsonl",
            "drift_repair_plans.jsonl",
        ],
        "operator_action_required": True,   # always True
        "status": "RECONCILED",
    }

    # Step 6: Append log + write latest
    try:
        append_reconciliation_log(record, runtime_root)
    except Exception:
        pass

    try:
        summary = {
            "ts": _now(),
            "last_reconciliation_id": reconciliation_id,
            "execution_id": execution_id,
            "finding_id": finding_id,
            "operator_id": operator_id,
            "verification_status": verification_status,
            "drift_state": drift_state,
            "governance_recommendation": recommendation,
            "operator_action_required": True,
        }
        save_reconciliation_latest(summary, runtime_root)
    except Exception:
        pass

    # Step 7: Return result
    return {
        "ok": True,
        "reconciliation_id": reconciliation_id,
        "execution_id": execution_id,
        "finding_id": finding_id,
        "verification_status": verification_status,
        "drift_state": drift_state,
        "governance_recommendation": recommendation,
        "operator_action_required": True,
    }
