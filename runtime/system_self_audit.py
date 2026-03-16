"""AG-57: System Self-Audit Layer.

Validates the integrity of the full supervisory governance stack
from AG-47 through AG-56. Emits a system self-audit verdict.

Audit-only — no mutation, no auto-correction, no repair execution,
no baseline mutation, no governance outcome enforcement.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.system_self_audit_policy import (
    AUDIT_VERDICTS,
    REQUIRED_ARTIFACTS,
    COHERENCE_CHECKS,
    derive_verdict,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rt(runtime_root: str | None = None) -> str:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    return rt


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _present(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_self_awareness_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_self_awareness_latest.json"),
        "data":    _read_json(state / "runtime_self_awareness_latest.json") or {},
    }


def load_trust_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": (
            _present(state / "runtime_claim_trust_latest.json") and
            _present(state / "runtime_claim_trust_index.json")
        ),
        "data": _read_json(state / "runtime_claim_trust_latest.json") or {},
    }


def load_guidance_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_trust_guidance_latest.json"),
        "data":    _read_json(state / "runtime_trust_guidance_latest.json") or {},
    }


def load_governance_gate_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_governance_gate_latest.json"),
        "data":    _read_json(state / "runtime_governance_gate_latest.json") or {},
    }


def load_decision_integrity_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_operator_decision_integrity_latest.json"),
        "data":    _read_json(state / "runtime_operator_decision_integrity_latest.json") or {},
    }


def load_alert_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_governance_alerts_latest.json"),
        "data":    _read_json(state / "runtime_governance_alerts_latest.json") or {},
    }


def load_dashboard_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    rt = _rt(runtime_root)
    state = Path(rt) / "state"
    return {
        "present": _present(state / "runtime_supervision_dashboard_latest.json"),
        "data":    _read_json(state / "runtime_supervision_dashboard_latest.json") or {},
    }


# ---------------------------------------------------------------------------
# Coherence verification
# ---------------------------------------------------------------------------

def verify_stack_coherence(
    sa_data: dict[str, Any],
    trust_data: dict[str, Any],
    guidance_data: dict[str, Any],
    gate_data: dict[str, Any],
    integrity_data: dict[str, Any],
    alert_data: dict[str, Any],
    dashboard_data: dict[str, Any],
) -> dict[str, Any]:
    """Verify coherence of the full governance stack."""
    checks: dict[str, bool] = {
        "self_awareness_present":  sa_data.get("present", False),
        "trust_index_present":     trust_data.get("present", False),
        "guidance_present":        guidance_data.get("present", False),
        "governance_gate_present": gate_data.get("present", False),
        "integrity_present":       integrity_data.get("present", False),
        "alerts_present":          alert_data.get("present", False),
        "dashboard_present":       dashboard_data.get("present", False),
    }

    missing: list[str] = [k for k, v in checks.items() if not v]

    # Additional coherence: dashboard should reference trust and alerts if both present
    incoherent: list[str] = []
    if (trust_data.get("present") and dashboard_data.get("present")):
        dash = dashboard_data.get("data", {})
        if "trust_index" not in dash:
            incoherent.append("dashboard_missing_trust_index_section")
    if (alert_data.get("present") and dashboard_data.get("present")):
        dash = dashboard_data.get("data", {})
        if "alert_count" not in dash:
            incoherent.append("dashboard_missing_alert_count")

    verdict = derive_verdict(len(missing), len(incoherent), len(COHERENCE_CHECKS))

    return {
        "checks":          checks,
        "missing":         missing,
        "incoherent":      incoherent,
        "missing_count":   len(missing),
        "incoherent_count": len(incoherent),
        "verdict":         verdict,
    }


# ---------------------------------------------------------------------------
# Artifact map audit
# ---------------------------------------------------------------------------

def audit_required_artifacts(runtime_root: str | None = None) -> dict[str, Any]:
    """Check which required artifacts are present/missing."""
    rt = _rt(runtime_root)
    state = Path(rt) / "state"

    results: dict[str, dict] = {}
    all_present = True
    for layer, filenames in REQUIRED_ARTIFACTS.items():
        layer_ok = all(_present(state / fn) for fn in filenames)
        results[layer] = {
            "present":  layer_ok,
            "files":    filenames,
            "missing":  [fn for fn in filenames if not _present(state / fn)],
        }
        if not layer_ok:
            all_present = False

    return {"all_present": all_present, "layers": results}


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_system_self_audit_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-57 system self-audit report."""
    rt = _rt(runtime_root)

    sa_data        = load_self_awareness_outputs(rt)
    trust_data     = load_trust_outputs(rt)
    guidance_data  = load_guidance_outputs(rt)
    gate_data      = load_governance_gate_outputs(rt)
    integrity_data = load_decision_integrity_outputs(rt)
    alert_data     = load_alert_outputs(rt)
    dashboard_data = load_dashboard_outputs(rt)

    coherence = verify_stack_coherence(
        sa_data, trust_data, guidance_data, gate_data,
        integrity_data, alert_data, dashboard_data,
    )

    artifact_audit = audit_required_artifacts(rt)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":           ts,
        "run_id":       str(uuid.uuid4()),
        "verdict":      coherence["verdict"],
        "coherence":    coherence,
        "artifact_audit": artifact_audit,
        "missing_count":   coherence["missing_count"],
        "incoherent_count": coherence["incoherent_count"],
        "gaps": coherence["missing"] + coherence["incoherent"],
        "evidence_refs": list(REQUIRED_ARTIFACTS.keys()),
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_system_self_audit(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-57 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_system_self_audit_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_system_self_audit_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":              report["ts"],
        "run_id":          report["run_id"],
        "verdict":         report["verdict"],
        "missing_count":   report["missing_count"],
        "incoherent_count": report["incoherent_count"],
        "gaps":            report["gaps"],
    }
    _atomic_write(state_dir / "runtime_system_self_audit_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_system_self_audit(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-57 system self-audit and persist outputs."""
    try:
        report = build_system_self_audit_report(runtime_root)
        store_system_self_audit(report, runtime_root)
        return {
            "ok":              True,
            "verdict":         report["verdict"],
            "missing_count":   report["missing_count"],
            "incoherent_count": report["incoherent_count"],
            "gaps":            report["gaps"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
