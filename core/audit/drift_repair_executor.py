"""AG-34: Drift Repair Executor.

Supervised execution orchestrator for approved AG-33 repair plans.

Invariants:
  - only executes plans with status == APPROVED and full approval metadata
  - only touches files listed in approved_target_files
  - captures before/after state (sha256 + mtime) for every target file
  - runs post-repair verification; result is PASSED | FAILED | INCONCLUSIVE
  - never modifies drift_finding_status.json (AG-32 owns finding lifecycle)
  - never modifies audit_baseline.py
  - never auto-approves plans
  - never closes findings

Public API:
  run_supervised_repair_execution(plan_id, operator_id, runtime_root=None) -> dict
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from core.audit.repair_execution_store import (
    append_repair_execution_log,
    new_execution_id,
    save_repair_execution_latest,
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
# Forbidden paths — hard-stops regardless of approved_target_files
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = (
    ".env",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    "credentials",
    "keychain",
    "audit_baseline.py",
    "drift_finding_status.json",
    "drift_governance_log.jsonl",
)

_FORBIDDEN_PREFIXES = (
    "/",    # absolute paths
    "~",    # home-dir expansions
    "*",    # wildcard
)


def _is_forbidden_target(path: str) -> bool:
    lp = path.lower()
    for pat in _FORBIDDEN_PATTERNS:
        if pat in lp:
            return True
    for prefix in _FORBIDDEN_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Approved plan loader
# ---------------------------------------------------------------------------

def list_approved_repair_plans(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return only plans that have full approval metadata and status == APPROVED."""
    try:
        plans_path = _state_dir(runtime_root) / "drift_repair_plans.jsonl"
        if not plans_path.exists():
            return []
        approved = []
        for line in plans_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                plan = json.loads(line)
                if _plan_is_approved(plan):
                    approved.append(plan)
            except Exception:
                pass
        return approved
    except Exception:
        return []


def _plan_is_approved(plan: dict[str, Any]) -> bool:
    """Check that a plan has the minimum approval contract."""
    if plan.get("status") != "APPROVED":
        return False
    required = ("plan_id", "finding_id", "operator_id", "approved_at",
                "approved_target_files", "approved_action_scope")
    return all(bool(plan.get(f)) for f in required)


def _load_plan_by_id(plan_id: str, runtime_root: str | None = None) -> dict[str, Any] | None:
    try:
        plans_path = _state_dir(runtime_root) / "drift_repair_plans.jsonl"
        if not plans_path.exists():
            return None
        for line in plans_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                plan = json.loads(line)
                if plan.get("plan_id") == plan_id:
                    return plan
            except Exception:
                pass
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------

def validate_execution_scope(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate that a plan is within safe execution boundaries.

    Returns:
      {"verdict": "ALLOW" | "BLOCK" | "ESCALATE", "reason": str}
    """
    # Must be APPROVED
    if plan.get("status") != "APPROVED":
        return {"verdict": "BLOCK", "reason": f"plan status is {plan.get('status')!r}, expected APPROVED"}

    # Required approval fields
    for field in ("plan_id", "finding_id", "operator_id", "approved_at",
                  "approved_target_files", "approved_action_scope"):
        if not plan.get(field):
            return {"verdict": "BLOCK", "reason": f"missing required approval field: {field}"}

    approved_files = plan.get("approved_target_files", [])
    if not approved_files:
        return {"verdict": "BLOCK", "reason": "approved_target_files is empty"}

    # Check for wildcards / absolute paths / forbidden targets
    for target in approved_files:
        if _is_forbidden_target(str(target)):
            return {"verdict": "BLOCK", "reason": f"target {target!r} is forbidden or matches secret/governance pattern"}

    # Check target_files match approved_target_files
    declared_targets = plan.get("target_files", [])
    approved_set = set(str(f) for f in approved_files)
    for target in declared_targets:
        if str(target) not in approved_set and not str(target).startswith("$LUKA_RUNTIME_ROOT"):
            return {
                "verdict": "ESCALATE",
                "reason": f"target {target!r} in target_files but not in approved_target_files",
            }

    return {"verdict": "ALLOW", "reason": "all scope checks passed"}


# ---------------------------------------------------------------------------
# State capture
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def capture_pre_repair_state(plan: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    """Capture before-state for all approved target files.

    Returns evidence dict with 'snapshots' list and 'ts'.
    """
    root = repo_root or Path(os.environ.get("LUKA_RUNTIME_ROOT", "")).parent
    approved_files = plan.get("approved_target_files", [])
    snapshots = []
    for rel in approved_files:
        p = root / str(rel) if not str(rel).startswith("$") else None
        if p is not None:
            snapshots.append({
                "path": str(rel),
                "exists_before": p.exists(),
                "sha256_before": _sha256_file(p),
                "mtime_before": p.stat().st_mtime if p.exists() else None,
            })
        else:
            snapshots.append({
                "path": str(rel),
                "exists_before": False,
                "sha256_before": "",
                "mtime_before": None,
            })
    return {"ts": _now(), "snapshots": snapshots}


def capture_post_repair_state(plan: dict[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    """Capture after-state for all approved target files."""
    root = repo_root or Path(os.environ.get("LUKA_RUNTIME_ROOT", "")).parent
    approved_files = plan.get("approved_target_files", [])
    snapshots = []
    for rel in approved_files:
        p = root / str(rel) if not str(rel).startswith("$") else None
        if p is not None:
            snapshots.append({
                "path": str(rel),
                "exists_after": p.exists(),
                "sha256_after": _sha256_file(p),
                "mtime_after": p.stat().st_mtime if p.exists() else None,
            })
        else:
            snapshots.append({
                "path": str(rel),
                "exists_after": False,
                "sha256_after": "",
                "mtime_after": None,
            })
    return {"ts": _now(), "snapshots": snapshots}


# ---------------------------------------------------------------------------
# Bounded execution
# ---------------------------------------------------------------------------

def execute_repair_plan(plan: dict[str, Any], operator_id: str) -> dict[str, Any]:
    """Execute the approved repair plan's action list in a bounded way.

    Current implementation:
      - Dry execution model: records proposed_actions as executed_actions
      - Does NOT apply free-form code changes — only records what was approved
      - Actual file mutations require explicit CLEC task submission (future bridge)
      - Returns execution summary

    This is intentionally conservative: AG-34 v1 proves the execution boundary,
    evidence collection, and verification pipeline. File-level patching is
    delegated to CLEC executor when operator submits an actual patch task.
    """
    proposed_actions = plan.get("proposed_actions", [])
    executed_actions = list(proposed_actions)  # record approved action list as executed

    return {
        "ts": _now(),
        "operator_id": operator_id,
        "plan_id": plan.get("plan_id"),
        "finding_id": plan.get("finding_id"),
        "executed_actions": executed_actions,
        "execution_model": "dry_record",  # v1: records actions; actual mutation via CLEC
        "note": "AG-34 v1: action list recorded for operator evidence. File mutation: submit CLEC task.",
    }


# ---------------------------------------------------------------------------
# Post-repair verification
# ---------------------------------------------------------------------------

def run_post_repair_verification(
    plan: dict[str, Any],
    execution: dict[str, Any],
    pre_state: dict[str, Any],
    post_state: dict[str, Any],
) -> dict[str, Any]:
    """Run post-repair verification checks.

    Checks:
      1. Execution recorded executed_actions
      2. All approved target files still exist (or exist_after matches expectation)
      3. Optional: syntax check for .py files

    Returns:
      {"verification_status": "PASSED"|"FAILED"|"INCONCLUSIVE", "checks": [...]}
    """
    checks = []
    failed = False
    inconclusive = False

    # Check 1: execution produced action record
    if not execution.get("executed_actions"):
        checks.append({"check": "actions_recorded", "result": "FAILED", "detail": "no executed_actions"})
        failed = True
    else:
        checks.append({"check": "actions_recorded", "result": "PASSED",
                       "detail": f"{len(execution['executed_actions'])} actions recorded"})

    # Check 2: post-state captured
    post_snaps = post_state.get("snapshots", [])
    if not post_snaps:
        checks.append({"check": "post_state_captured", "result": "INCONCLUSIVE", "detail": "no post snapshots"})
        inconclusive = True
    else:
        checks.append({"check": "post_state_captured", "result": "PASSED",
                       "detail": f"{len(post_snaps)} file snapshots"})

    # Check 3: Python syntax check for .py target files (best-effort)
    approved_files = plan.get("approved_target_files", [])
    for rel in approved_files:
        if not str(rel).endswith(".py") or str(rel).startswith("$"):
            continue
        repo_root = Path(os.environ.get("LUKA_RUNTIME_ROOT", "")).parent
        fp = repo_root / str(rel)
        if not fp.exists():
            checks.append({"check": f"syntax:{rel}", "result": "INCONCLUSIVE",
                           "detail": "file not found post-repair"})
            inconclusive = True
            continue
        try:
            result = subprocess.run(
                ["python3", "-m", "py_compile", str(fp)],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                checks.append({"check": f"syntax:{rel}", "result": "PASSED"})
            else:
                checks.append({"check": f"syntax:{rel}", "result": "FAILED",
                               "detail": result.stderr.decode()[:200]})
                failed = True
        except Exception as exc:
            checks.append({"check": f"syntax:{rel}", "result": "INCONCLUSIVE", "detail": str(exc)})
            inconclusive = True

    if failed:
        verification_status = "FAILED"
    elif inconclusive and not failed:
        verification_status = "INCONCLUSIVE"
    else:
        verification_status = "PASSED"

    return {
        "ts": _now(),
        "verification_status": verification_status,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# End-to-end orchestrator
# ---------------------------------------------------------------------------

def run_supervised_repair_execution(
    plan_id: str,
    operator_id: str,
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """End-to-end AG-34 supervised repair execution flow.

    Steps:
      1. Load approved plan
      2. Validate execution scope
      3. Capture pre-repair state
      4. Execute bounded repair
      5. Capture post-repair state
      6. Run post-repair verification
      7. Write execution log record (append-only)
      8. Write latest execution summary (atomic)
      9. Return result

    Does NOT modify drift_finding_status.json.
    Does NOT modify audit_baseline.py.
    Does NOT close findings.
    """
    execution_id = new_execution_id()
    ts_start = _now()

    # Step 1: Load plan
    plan = _load_plan_by_id(plan_id, runtime_root)
    if plan is None:
        return {
            "ok": False,
            "execution_id": execution_id,
            "reason": f"plan_id {plan_id!r} not found",
            "status": "FAILED",
        }

    # Step 2: Validate scope
    scope_result = validate_execution_scope(plan)
    if scope_result["verdict"] != "ALLOW":
        record: dict[str, Any] = {
            "ts": ts_start,
            "execution_id": execution_id,
            "plan_id": plan_id,
            "finding_id": plan.get("finding_id", ""),
            "operator_id": operator_id,
            "target_files": plan.get("approved_target_files", []),
            "before_state": [],
            "after_state": [],
            "executed_actions": [],
            "verification_status": "FAILED",
            "status": "FAILED",
            "scope_verdict": scope_result["verdict"],
            "scope_reason": scope_result["reason"],
            "operator_approval_ref": plan.get("approved_at", ""),
        }
        try:
            append_repair_execution_log(record, runtime_root)
        except Exception:
            pass
        return {
            "ok": False,
            "execution_id": execution_id,
            "reason": f"scope validation {scope_result['verdict']}: {scope_result['reason']}",
            "status": "FAILED",
        }

    # Derive repo root from LUKA_RUNTIME_ROOT parent
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    repo_root = Path(rt).parent if rt else None

    # Step 3: Capture pre-repair state
    try:
        pre_state = capture_pre_repair_state(plan, repo_root)
    except Exception as exc:
        pre_state = {"ts": ts_start, "snapshots": [], "error": str(exc)}

    # Step 4: Execute bounded repair
    try:
        execution_result = execute_repair_plan(plan, operator_id)
    except Exception as exc:
        execution_result = {"executed_actions": [], "error": str(exc)}

    # Step 5: Capture post-repair state
    try:
        post_state = capture_post_repair_state(plan, repo_root)
    except Exception as exc:
        post_state = {"ts": _now(), "snapshots": [], "error": str(exc)}

    # Step 6: Run verification
    try:
        verification = run_post_repair_verification(plan, execution_result, pre_state, post_state)
    except Exception as exc:
        verification = {"verification_status": "INCONCLUSIVE", "checks": [], "error": str(exc)}

    verification_status = verification.get("verification_status", "INCONCLUSIVE")
    exec_status = "EXECUTED" if not execution_result.get("error") else "FAILED"

    # Step 7: Build execution record
    full_record: dict[str, Any] = {
        "ts": ts_start,
        "execution_id": execution_id,
        "plan_id": plan_id,
        "finding_id": plan.get("finding_id", ""),
        "operator_id": operator_id,
        "target_files": plan.get("approved_target_files", []),
        "before_state": pre_state.get("snapshots", []),
        "after_state": post_state.get("snapshots", []),
        "executed_actions": execution_result.get("executed_actions", []),
        "execution_model": execution_result.get("execution_model", ""),
        "verification_status": verification_status,
        "verification_checks": verification.get("checks", []),
        "status": exec_status,
        "operator_approval_ref": plan.get("approved_at", ""),
        "scope_verdict": scope_result["verdict"],
    }

    # Step 8: Append log + write latest
    try:
        append_repair_execution_log(full_record, runtime_root)
    except Exception:
        pass

    try:
        summary = {
            "ts": _now(),
            "last_execution_id": execution_id,
            "plan_id": plan_id,
            "finding_id": plan.get("finding_id", ""),
            "operator_id": operator_id,
            "status": exec_status,
            "verification_status": verification_status,
        }
        save_repair_execution_latest(summary, runtime_root)
    except Exception:
        pass

    # Step 9: Return result
    return {
        "ok": exec_status == "EXECUTED",
        "execution_id": execution_id,
        "plan_id": plan_id,
        "finding_id": plan.get("finding_id", ""),
        "status": exec_status,
        "verification_status": verification_status,
        "executed_actions": execution_result.get("executed_actions", []),
        "scope_verdict": scope_result["verdict"],
    }
