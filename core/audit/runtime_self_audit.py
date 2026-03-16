"""AG-31: Runtime Self-Audit Layer — main orchestrator.

Compares:
  - canonical architecture (diagram + capability matrix)
  - actual codebase reality (modules, imports, routes)
  - runtime state ($LUKA_RUNTIME_ROOT/state/)
  - governance boundary (operator gates on write endpoints)

Produces three outputs (all under $LUKA_RUNTIME_ROOT/state/):
  - runtime_self_audit.json   — machine-readable summary (latest run)
  - drift_findings.jsonl      — append-only ledger of findings
  (runtime_self_audit.md written to g/reports/architecture/ relative to ROOT)

Public API:
  run_runtime_self_audit(runtime_root=None) -> dict

AG-31 invariant:
  READ-ONLY except its own three output files.
  Never mutates policy state, registry, or any other runtime artifact.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import time
import traceback
import uuid
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Canonical component registry
# All module paths verified against main @ 2026-03-16.
# ---------------------------------------------------------------------------

CANONICAL_COMPONENTS: list[dict[str, Any]] = [
    # ── Layer 1: Kernel ──────────────────────────────────────────────────────
    {
        "id": "task_dispatcher",
        "ag": 1, "layer": "L1_kernel",
        "module": "core.task_dispatcher",
        "state_file": None,
        "canonical_importer": None,           # entrypoint — not imported by others
        "operator_gate": False,
        "description": "Inbox watcher + dispatch loop",
    },
    {
        "id": "circuit_breaker",
        "ag": 6, "layer": "L1_kernel",
        "module": "core.circuit_breaker",
        "state_file": None,
        "canonical_importer": "core.task_dispatcher",
        "operator_gate": False,
        "description": "Trip/reset guard (fulfills 'runtime_guardian' in SOT)",
    },
    {
        # SOT and architecture diagram use the name 'runtime_guardian'.
        # No such file exists — function is split across circuit_breaker + phase1a_resolver.
        # This entry exists solely to trigger the accepted naming_drift_only finding.
        "id": "runtime_guardian",
        "ag": 1, "layer": "L1_kernel",
        "module": "core.runtime_guardian",       # SOT name — does not exist on disk
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": False,
        "known_drift_key": "runtime_guardian_name_gap",   # accepted baseline
        "description": "SOT alias — fulfilled by circuit_breaker + phase1a_resolver",
    },
    {
        "id": "phase1a_resolver",
        "ag": 1, "layer": "L1_kernel",
        "module": "core.phase1a_resolver",
        "state_file": None,
        "canonical_importer": "core.task_dispatcher",
        "operator_gate": False,
        "description": "Inbound gate: schema validation + hardpath guard",
    },
    {
        "id": "router",
        "ag": 1, "layer": "L1_kernel",
        "module": "core.router",
        "state_file": None,
        "canonical_importer": "core.task_dispatcher",
        "operator_gate": False,
        "description": "Propose/execute/audit with policy enforcement",
    },
    {
        "id": "clec_executor",
        "ag": 1, "layer": "L1_kernel",
        "module": "core.clec_executor",
        "state_file": None,
        "canonical_importer": "core.router",
        "operator_gate": False,
        "description": "Executes CLEC ops: write_text, mkdir, copy, patch_apply, run",
    },
    # ── Layer 2: Runtime State ────────────────────────────────────────────────
    {
        "id": "config",
        "ag": 1, "layer": "L2_runtime_state",
        "module": "core.config",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": False,
        "description": "ROOT resolution + canonical paths",
    },
    # ── Layer 3: Observability ────────────────────────────────────────────────
    {
        "id": "run_provenance",
        "ag": 5, "layer": "L3_observability",
        "module": "core.run_provenance",
        "state_file": None,        # writes to observability/, not state/
        "canonical_importer": "core.task_dispatcher",
        "operator_gate": False,
        "description": "Records input/output hash per execution",
    },
    {
        "id": "timeline",
        "ag": 5, "layer": "L3_observability",
        "module": "core.timeline",
        "state_file": None,
        "canonical_importer": "core.task_dispatcher",
        "operator_gate": False,
        "description": "Lifecycle event emitter",
    },
    # ── Layer 4: Mission Control ──────────────────────────────────────────────
    {
        "id": "mission_control_server",
        "ag": 9, "layer": "L4_mission_control",
        "module": "interface.operator.mission_control_server",
        "state_file": None,
        "canonical_importer": None,           # launched by sovereign_loop
        "operator_gate": False,
        "description": "FastAPI server — all API surfaces",
    },
    # ── Layer 5: Run Interpretation ───────────────────────────────────────────
    {
        "id": "run_interpreter",
        "ag": 12, "layer": "L5_run_interpretation",
        "module": "tools.ops.run_interpreter",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": False,
        "description": "interpret_run() → COMPLETE/PARTIAL/MISSING_PROOF/INCONSISTENT",
    },
    # ── Layer 6: Decision Persistence ─────────────────────────────────────────
    {
        "id": "decision_engine",
        "ag": 18, "layer": "L6_decision_persistence",
        "module": "tools.ops.decision_engine",
        "state_file": "decision_log.jsonl",
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "classify_once() → nominal/drift_detected",
    },
    {
        "id": "control_plane_persistence",
        "ag": 18, "layer": "L6_decision_persistence",
        "module": "tools.ops.control_plane_persistence",
        "state_file": "decision_latest.json",
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "decision_log.jsonl + decision_latest.json writer",
    },
    # ── Layer 7: Planner / Executor / Verifier ────────────────────────────────
    {
        "id": "feedback_loop",
        "ag": 17, "layer": "L7_planner_executor_verifier",
        "module": "core.orchestrator.feedback_loop",
        "state_file": None,
        "canonical_importer": "tools.ops.sovereign_loop",  # intentional lazy path
        "operator_gate": False,
        "description": "Planner/executor/verifier loop — wired via sovereign_loop",
    },
    {
        "id": "feedback_router",
        "ag": 18, "layer": "L7_planner_executor_verifier",
        "module": "core.orchestrator.feedback_router",
        "state_file": None,
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "Signal routing for feedback loop",
    },
    {
        "id": "phase1d_result_gate",
        "ag": 19, "layer": "L7_planner_executor_verifier",
        "module": "core.phase1d_result_gate",
        "state_file": None,
        "canonical_importer": "core.router",
        "operator_gate": False,
        "description": "Outbound result gate: sanitization + evidence minimum",
    },
    # ── Layer 8: Adaptive Remediation ─────────────────────────────────────────
    {
        "id": "adaptation_engine",
        "ag": 20, "layer": "L8_adaptive_remediation",
        "module": "core.adaptation.adaptation_engine",
        "state_file": "adaptation_log.jsonl",
        "canonical_importer": None,
        "operator_gate": False,
        "description": "Canonical AG-20 adaptive remediation engine",
    },
    {
        "id": "adaptation_store",
        "ag": 20, "layer": "L8_adaptive_remediation",
        "module": "core.adaptation.adaptation_store",
        "state_file": "adaptation_latest.json",
        "canonical_importer": "core.adaptation.adaptation_engine",
        "operator_gate": False,
        "description": "Adaptation state persistence",
    },
    {
        "id": "recovery_engine",
        "ag": 28, "layer": "L8_adaptive_remediation",
        "module": "core.recovery.recovery_engine",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": False,
        "description": "AG-28 autonomous recovery engine",
    },
    # ── Layer 9: Learning Plane ───────────────────────────────────────────────
    {
        "id": "observation_store",
        "ag": 21, "layer": "L9_learning_plane",
        "module": "learning.observation_store",
        "state_file": "learning_observations.jsonl",  # first-run optional
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "AG-21 observation store",
    },
    {
        "id": "pattern_extractor",
        "ag": 21, "layer": "L9_learning_plane",
        "module": "learning.pattern_extractor",
        "state_file": None,
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "Pattern extraction from observations",
    },
    {
        "id": "policy_candidates",
        "ag": 21, "layer": "L9_learning_plane",
        "module": "learning.policy_candidates",
        "state_file": None,
        "canonical_importer": "core.orchestrator.feedback_loop",
        "operator_gate": False,
        "description": "Policy candidate generation from patterns",
    },
    # ── Layer 10: Policy Control Plane ────────────────────────────────────────
    {
        "id": "policy_registry",
        "ag": 22, "layer": "L10_policy_control",
        "module": "core.policy.policy_registry",
        "state_file": "policy_registry.json",
        "canonical_importer": None,
        "operator_gate": False,
        "description": "Active policy registry",
    },
    {
        "id": "policy_promoter",
        "ag": 22, "layer": "L10_policy_control",
        "module": "core.policy.policy_promoter",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": True,   # promote_policy requires operator_id
        "description": "Policy promotion — operator_id required",
    },
    {
        "id": "promotion_verifier",
        "ag": 22, "layer": "L10_policy_control",
        "module": "core.policy.promotion_verifier",
        "state_file": None,
        "canonical_importer": "core.policy.policy_promoter",
        "operator_gate": False,
        "description": "Pre-promotion verification",
    },
    {
        "id": "policy_lifecycle",
        "ag": 23, "layer": "L10_policy_control",
        "module": "core.policy.policy_lifecycle",
        "state_file": "policy_activation_log.jsonl",
        "canonical_importer": None,
        "operator_gate": True,   # revoke/deprecate/supersede require operator_id
        "description": "Policy lifecycle: revoke/deprecate/supersede/expire",
    },
    {
        "id": "effectiveness_verifier",
        "ag": 29, "layer": "L10_policy_control",
        "module": "core.policy.effectiveness_verifier",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": True,
        "description": "AG-29 effectiveness verification — measure + recommend",
    },
    {
        "id": "outcome_router",
        "ag": 30, "layer": "L10_policy_control",
        "module": "core.policy.outcome_router",
        "state_file": None,
        "canonical_importer": None,
        "operator_gate": False,
        "description": "AG-30 verdict → operator-facing recommended action",
    },
    {
        "id": "outcome_store",
        "ag": 30, "layer": "L10_policy_control",
        "module": "core.policy.outcome_store",
        "state_file": "policy_outcome_governance.jsonl",  # first-run optional
        "canonical_importer": None,
        "operator_gate": False,
        "description": "AG-30 governance record persistence",
    },
]


# ---------------------------------------------------------------------------
# Canonical architecture routes (subset from diagram + capability matrix)
# Routes NOT in this list but present in MCS → API_exposed_but_not_in_diagram
# ---------------------------------------------------------------------------

CANONICAL_API_ROUTES: frozenset[str] = frozenset({
    # Layer 3 — Observability
    "GET /api/activity",
    # Layer 4 — Mission Control
    "GET /health",
    "GET /api/runtime_status",
    "GET /api/operator_status",
    "GET /api/proof_artifacts",
    "GET /api/qs_runs",
    # Layer 5 — Run Interpretation
    "GET /api/decisions/latest",
    # Layer 6 — Decision Persistence
    "POST /api/decisions/latest/approve",
    "POST /api/decisions/latest/reject",
    "POST /api/decisions/latest/execute",
    # Layer 8 — Adaptive Remediation
    "GET /api/remediation_history",
    "GET /api/remediation_queue",
    # Layer 9 — Learning Plane (no canonical API — internal only)
    # Layer 10 — Policy Control
    "GET /api/policies",
    "POST /api/promote_policy",
    "POST /api/revoke_policy",
    "POST /api/deprecate_policy",
    "POST /api/supersede_policy",
    "GET /api/policy_effectiveness",
    "POST /api/verify_policy_effectiveness",
    "GET /api/policy_outcome_governance",
    "POST /api/policy_outcome_action",
    "POST /api/run_outcome_governance",
    # Layer 10 — Governance outcomes
    "GET /api/policy_verification_log",
    "GET /api/policy_outcome_log",
})

# Write routes that MUST have operator_id gate (handler must return 403 without it)
OPERATOR_GATED_WRITE_ROUTES: list[dict[str, str]] = [
    {"route": "POST /api/promote_policy",           "api_file": "api_policies.py",      "handler": "promote_policy_endpoint"},
    {"route": "POST /api/revoke_policy",            "api_file": "api_policies.py",      "handler": "revoke_policy_endpoint"},
    {"route": "POST /api/deprecate_policy",         "api_file": "api_policies.py",      "handler": "deprecate_policy_endpoint"},
    {"route": "POST /api/supersede_policy",         "api_file": "api_policies.py",      "handler": "supersede_policy_endpoint"},
    {"route": "POST /api/verify_policy_effectiveness", "api_file": "api_effectiveness.py", "handler": "verify_policy_endpoint"},
    {"route": "POST /api/policy_outcome_action",    "api_file": "api_outcome.py",       "handler": "outcome_action_endpoint"},
    {"route": "POST /api/run_outcome_governance",   "api_file": "api_outcome.py",       "handler": "run_outcome_governance_endpoint"},
    # AG-31 self-audit trigger
    {"route": "POST /api/self_audit/run",           "api_file": "api_self_audit.py",    "handler": "self_audit_run_endpoint"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str) -> Path:
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _repo_root() -> Path:
    """Return the repository root (directory containing this file's core/ parent)."""
    return Path(__file__).resolve().parent.parent.parent


def _new_finding(
    drift_class: str,
    component: str,
    evidence: str,
    accepted: bool = False,
    drift_key: str = "",
    notes: str = "",
    severity_override: str = "",
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:8],
        "drift_class": drift_class,
        "component": component,
        "evidence": evidence,
        "accepted": accepted,
        "drift_key": drift_key,
        "notes": notes,
        **({"severity_override": severity_override} if severity_override else {}),
    }


# ---------------------------------------------------------------------------
# Inspection steps
# ---------------------------------------------------------------------------

def _inspect_components(repo_root: Path, runtime_root: str) -> list[dict[str, Any]]:
    """Check each canonical component for existence and canonical wiring."""
    from core.audit.audit_baseline import is_known_drift

    findings: list[dict[str, Any]] = []
    state_d = Path(runtime_root) / "state"

    for comp in CANONICAL_COMPONENTS:
        module_path = comp["module"]
        comp_id = comp["id"]

        # 1. Module existence
        spec = importlib.util.find_spec(module_path)
        if spec is None:
            # If the component has an explicit known_drift_key, this is an accepted naming drift
            explicit_dk = comp.get("known_drift_key", "")
            if explicit_dk and is_known_drift(explicit_dk):
                findings.append(_new_finding(
                    drift_class="naming_drift_only",
                    component=module_path,
                    evidence=f"importlib.util.find_spec('{module_path}') returned None — SOT naming alias",
                    accepted=True,
                    drift_key=explicit_dk,
                    notes=f"ag={comp['ag']} layer={comp['layer']} {comp.get('description', '')}",
                ))
            else:
                dk = explicit_dk or f"{comp_id}_name_gap"
                accepted = is_known_drift(dk)
                findings.append(_new_finding(
                    drift_class="expected_by_SOT_but_missing" if not accepted else "naming_drift_only",
                    component=module_path,
                    evidence=f"importlib.util.find_spec('{module_path}') returned None",
                    accepted=accepted,
                    drift_key=dk,
                    notes=f"ag={comp['ag']} layer={comp['layer']}",
                ))
            continue  # can't check wiring without module

        # 2. Canonical wiring (if importer specified)
        importer = comp.get("canonical_importer")
        if importer:
            wired = _check_import_in_file(importer, module_path, repo_root)
            if not wired:
                # Check known accepted drift
                dk = f"{comp_id}_lazy_path" if "lazy" in comp.get("description", "") else f"{comp_id}_wiring"
                # Special-case: feedback_loop has accepted lazy wiring
                if comp_id == "feedback_loop":
                    dk = "feedback_loop_lazy_path"
                accepted = is_known_drift(dk)
                findings.append(_new_finding(
                    drift_class="exists_but_not_wired",
                    component=module_path,
                    evidence=(
                        f"Module exists but not imported in canonical importer '{importer}'. "
                        f"Source scan found no 'import' of '{module_path.split('.')[-1]}' in importer."
                    ),
                    accepted=accepted,
                    drift_key=dk,
                    notes=f"ag={comp['ag']} expected_importer={importer}",
                ))

        # 3. State file check
        state_file = comp.get("state_file")
        if state_file:
            sf_path = state_d / state_file
            if not sf_path.exists():
                from core.audit.audit_baseline import is_first_run_optional
                first_run = is_first_run_optional(state_file)
                findings.append(_new_finding(
                    drift_class="state_file_expected_but_not_produced",
                    component=f"{module_path} → {state_file}",
                    evidence=f"os.path.exists('{sf_path}') → False",
                    accepted=first_run,
                    drift_key="first_run_optional_state_files" if first_run else "",
                    notes="first-run optional" if first_run else "expected after at least one run",
                    severity_override="INFO" if first_run else "",
                ))

    return findings


def _check_import_in_file(importer_module: str, target_module: str, repo_root: Path) -> bool:
    """Return True if target_module is imported (in any form) inside importer_module's source."""
    # Convert module path to file path
    module_rel = importer_module.replace(".", "/") + ".py"
    # Try several base paths (tools/ is top-level, learning/ is top-level)
    candidates = [
        repo_root / module_rel,
        repo_root / "core" / module_rel,
    ]
    source_file: Path | None = None
    for c in candidates:
        if c.exists():
            source_file = c
            break
    if source_file is None:
        # Try direct path from repo_root
        direct = repo_root / module_rel
        if direct.exists():
            source_file = direct

    if source_file is None:
        return False

    try:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False

    # Check for any import reference — module name, last segment, or dotted path
    target_last = target_module.split(".")[-1]
    return (
        target_module in source
        or f"import {target_last}" in source
        or f"from {target_module}" in source
    )


def _inspect_routes(repo_root: Path) -> list[dict[str, Any]]:
    """Check MCS route registrations against canonical route list."""
    from core.audit.audit_baseline import is_known_drift

    findings: list[dict[str, Any]] = []
    mcs_path = repo_root / "interface" / "operator" / "mission_control_server.py"

    if not mcs_path.exists():
        findings.append(_new_finding(
            drift_class="expected_by_SOT_but_missing",
            component="interface.operator.mission_control_server",
            evidence="File not found on disk",
        ))
        return findings

    try:
        source = mcs_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        findings.append(_new_finding(
            drift_class="unknown",
            component="mission_control_server.py",
            evidence=f"Could not read MCS: {exc}",
        ))
        return findings

    # Extract all registered routes
    pattern = re.compile(
        r'app\.add_api_route\(\s*"([^"]+)"\s*,\s*\w+\s*,\s*methods=\[([^\]]+)\]',
        re.MULTILINE,
    )
    registered: list[str] = []
    for m in pattern.finditer(source):
        path = m.group(1)
        methods_raw = m.group(2).replace('"', "").replace("'", "").split(",")
        for method in methods_raw:
            method = method.strip()
            if method:
                registered.append(f"{method} {path}")

    # Routes in MCS but not in canonical list
    for route in registered:
        if route not in CANONICAL_API_ROUTES:
            dk = "api_activity_name_gap" if "/api/activity" in route else ""
            accepted = bool(dk and is_known_drift(dk))
            findings.append(_new_finding(
                drift_class="API_exposed_but_not_in_diagram",
                component=route,
                evidence="Route registered in MCS but not listed in canonical architecture routes",
                accepted=accepted,
                drift_key=dk,
                severity_override="INFO",
            ))

    # Canonical routes not found in MCS
    for route in sorted(CANONICAL_API_ROUTES):
        if route not in registered:
            findings.append(_new_finding(
                drift_class="canonical_component_but_no_runtime_evidence",
                component=route,
                evidence="Canonical route not found in MCS app.add_api_route registrations",
                notes="Route may be registered under alias or in a try/except block",
            ))

    return findings


def _inspect_operator_gates(repo_root: Path) -> list[dict[str, Any]]:
    """Scan write-endpoint handlers for operator_id enforcement (403 gate)."""
    findings: list[dict[str, Any]] = []
    api_dir = repo_root / "interface" / "operator"

    for entry in OPERATOR_GATED_WRITE_ROUTES:
        route = entry["route"]
        api_file = entry["api_file"]
        handler = entry["handler"]
        file_path = api_dir / api_file

        if not file_path.exists():
            findings.append(_new_finding(
                drift_class="operator_gate_missing",
                component=f"{route} → {handler}",
                evidence=f"Handler file {api_file} not found on disk",
                notes="Cannot verify operator gate — file missing",
            ))
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            findings.append(_new_finding(
                drift_class="operator_gate_missing",
                component=f"{route} → {handler}",
                evidence=f"Could not read {api_file}: {exc}",
            ))
            continue

        has_gate = _handler_has_operator_gate(source, handler)
        if not has_gate:
            findings.append(_new_finding(
                drift_class="operator_gate_missing",
                component=f"{route} → {handler}",
                evidence=(
                    f"Source scan of {api_file}::{handler}: "
                    "no '403' + 'operator_id' enforcement pattern found in handler body"
                ),
                notes="GOVERNANCE_VIOLATION: write endpoint lacks operator approval gate",
            ))

    return findings


def _handler_has_operator_gate(source: str, handler_name: str) -> bool:
    """Return True if handler function contains operator_id + 403 enforcement."""
    # Find the function block — extract from 'async def handler_name' to next 'async def' or end
    pattern = re.compile(
        rf"async\s+def\s+{re.escape(handler_name)}\b.*?(?=\nasync\s+def\s|\nclass\s|\Z)",
        re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        # Try non-async def
        pattern2 = re.compile(
            rf"def\s+{re.escape(handler_name)}\b.*?(?=\ndef\s|\nclass\s|\Z)",
            re.DOTALL,
        )
        match = pattern2.search(source)

    if not match:
        # Function not found in file — fall back to whole-file scan
        return "operator_id" in source and "403" in source

    fn_body = match.group()

    # Direct check: handler itself enforces the gate
    if "operator_id" in fn_body and "403" in fn_body:
        return True

    # Delegation check: handler references operator_id (via helper return value or direct)
    # AND the file has a 403 gate in a helper function called by this handler.
    # This covers the pattern: policy_id, operator_id, err = _extract_policy_operator(body, request)
    if "operator_id" in fn_body and "403" in source:
        return True

    return False


def _inspect_test_coverage() -> list[dict[str, Any]]:
    """Check that each AG phase (17-31) has a test suite in core/verify/."""
    findings: list[dict[str, Any]] = []
    repo_root = _repo_root()
    verify_dir = repo_root / "core" / "verify"

    # AG phases with canonical implementation
    ag_phases_with_code = list(range(17, 32))  # AG-17 through AG-31

    for ag in ag_phases_with_code:
        pattern = f"test_ag{ag}_*.py"
        matches = list(verify_dir.glob(pattern))
        if not matches:
            findings.append(_new_finding(
                drift_class="canonical_component_but_no_runtime_evidence",
                component=f"AG-{ag} test suite",
                evidence=f"No file matching '{pattern}' found in core/verify/",
                severity_override="MEDIUM",
                notes=f"AG-{ag} has no test suite in core/verify/",
            ))

    return findings


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def _append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Append records to a JSONL file (creates if absent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _write_markdown(path: Path, result: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    """Write human-readable audit report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = result.get("summary", {})
    verdict = result.get("overall_verdict", "UNKNOWN")
    ts = result.get("ts", "")

    lines: list[str] = [
        "# AG-31 Runtime Self-Audit Report",
        "",
        f"**Generated:** {ts}",
        f"**Audit version:** {result.get('audit_version', '1.0')}",
        "",
        "---",
        "",
        "## Executive Verdict",
        "",
        f"**`{verdict}`**",
        "",
        f"- Total checks: {summary.get('total', 0)}",
        f"- Open findings: {summary.get('open', 0)}",
        f"- Accepted (baseline): {summary.get('accepted', 0)}",
        f"- Blocking drift: {summary.get('blocking_drift', 0)}",
        "",
        "---",
        "",
        "## Findings by Severity",
        "",
    ]

    open_findings = [f for f in findings if not f.get("accepted", False)]
    if not open_findings:
        lines.append("*No open findings.*")
    else:
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            sev_findings = [f for f in open_findings if f.get("severity") == sev]
            if sev_findings:
                lines.append(f"### {sev}")
                lines.append("")
                for f in sev_findings:
                    lines.append(f"- **{f.get('drift_class')}** — `{f.get('component')}`")
                    lines.append(f"  - Evidence: {f.get('evidence')}")
                    if f.get("notes"):
                        lines.append(f"  - Notes: {f.get('notes')}")
                lines.append("")

    lines += [
        "---",
        "",
        "## Accepted Drift (Baseline)",
        "",
    ]
    accepted_findings = [f for f in findings if f.get("accepted", False)]
    if not accepted_findings:
        lines.append("*No accepted drift items.*")
    else:
        for f in accepted_findings:
            lines.append(f"- **{f.get('drift_class')}** — `{f.get('component')}`")
            lines.append(f"  - Drift key: `{f.get('drift_key', '')}`")
            lines.append(f"  - {f.get('evidence')}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Blocking Drift",
        "",
    ]
    blocking_rank = {"DRIFT_DETECTED": 2, "GOVERNANCE_VIOLATION": 3}
    blocking = [
        f for f in open_findings
        if blocking_rank.get(str(f.get("effective_verdict", "")), 0) >= 2
    ]
    if not blocking:
        lines.append("*No blocking drift.*")
    else:
        for f in blocking:
            lines.append(f"- **{f.get('drift_class')}** — `{f.get('component')}`")
            lines.append(f"  - Evidence: {f.get('evidence')}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Recommended Next Actions",
        "",
    ]
    if verdict == "CONSISTENT":
        lines.append("System is consistent with canonical architecture. No action required.")
    elif verdict == "WIRED_WITH_GAPS":
        lines.append("Runtime works. Review MEDIUM+ findings and update architecture diagram if needed.")
    elif verdict == "DRIFT_DETECTED":
        lines.append("Blocking drift found. Investigate and resolve before next AG phase.")
    elif verdict == "GOVERNANCE_VIOLATION":
        lines.append("**CRITICAL**: One or more write endpoints lack operator gate.")
        lines.append("Resolve `operator_gate_missing` findings immediately.")

    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
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

def run_runtime_self_audit(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-31 runtime self-audit.

    Args:
        runtime_root: override LUKA_RUNTIME_ROOT env var (for testing)

    Returns:
        Full audit result dict (same structure as runtime_self_audit.json).

    Invariant:
        Only writes to:
          - $LUKA_RUNTIME_ROOT/state/runtime_self_audit.json
          - $LUKA_RUNTIME_ROOT/state/drift_findings.jsonl
          - <repo_root>/g/reports/architecture/runtime_self_audit.md
        Never modifies policy state, registry, or any other runtime artifact.
    """
    from core.audit.drift_classifier import classify_finding, summarize_findings

    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set and runtime_root not provided")

    repo_root = _repo_root()
    ts = _now()
    audit_id = uuid.uuid4().hex[:10]

    # ── Collect raw findings ──────────────────────────────────────────────────
    raw_findings: list[dict[str, Any]] = []
    errors: list[str] = []

    for step_name, step_fn in [
        ("components",     lambda: _inspect_components(repo_root, rt)),
        ("routes",         lambda: _inspect_routes(repo_root)),
        ("operator_gates", lambda: _inspect_operator_gates(repo_root)),
        ("test_coverage",  lambda: _inspect_test_coverage()),
    ]:
        try:
            raw_findings.extend(step_fn())
        except Exception as exc:
            errors.append(f"{step_name}: {exc}\n{traceback.format_exc()}")

    # ── Classify ──────────────────────────────────────────────────────────────
    classified = [classify_finding(f) for f in raw_findings]

    # ── Summarize ─────────────────────────────────────────────────────────────
    summary = summarize_findings(classified)

    result: dict[str, Any] = {
        "ts": ts,
        "audit_id": audit_id,
        "audit_version": "1.0",
        "overall_verdict": summary["overall_verdict"],
        "summary": summary,
        "findings": classified,
        "errors": errors,
        "layers": _layer_verdicts(classified),
    }

    # ── Persist outputs ───────────────────────────────────────────────────────
    state_d = _state_dir(rt)

    # 1. runtime_self_audit.json — latest run (overwrite)
    _write_json(state_d / "runtime_self_audit.json", result)

    # 2. drift_findings.jsonl — append-only
    ledger_records = [
        {
            "ts": ts,
            "audit_id": audit_id,
            "drift_class": f.get("drift_class"),
            "severity": f.get("severity"),
            "component": f.get("component"),
            "status": f.get("status"),
            "accepted": f.get("accepted"),
            "effective_verdict": f.get("effective_verdict"),
        }
        for f in classified
    ]
    _append_jsonl(state_d / "drift_findings.jsonl", ledger_records)

    # 3. runtime_self_audit.md — human-readable (overwrite)
    md_path = repo_root / "g" / "reports" / "architecture" / "runtime_self_audit.md"
    try:
        _write_markdown(md_path, result, classified)
    except Exception as exc:
        result.setdefault("errors", []).append(f"markdown write: {exc}")

    return result


def _layer_verdicts(findings: list[dict[str, Any]]) -> dict[str, str]:
    """Compute per-layer verdict from classified findings."""
    from core.audit.drift_classifier import _VERDICT_RANK, VERDICT_ORDER  # type: ignore[attr-defined]

    layer_worst: dict[str, str] = {}
    for f in findings:
        if f.get("accepted"):
            continue
        # Extract layer from notes field (format: "ag=N layer=Lx_name")
        notes = str(f.get("notes", ""))
        m = re.search(r"layer=(\S+)", notes)
        if not m:
            continue
        layer = m.group(1)
        ev = str(f.get("effective_verdict", "CONSISTENT"))
        current = layer_worst.get(layer, "CONSISTENT")
        if _VERDICT_RANK.get(ev, 0) > _VERDICT_RANK.get(current, 0):
            layer_worst[layer] = ev

    # Fill in CONSISTENT for all canonical layers
    for comp in CANONICAL_COMPONENTS:
        layer = comp["layer"]
        if layer not in layer_worst:
            layer_worst[layer] = "CONSISTENT"

    return dict(sorted(layer_worst.items()))
