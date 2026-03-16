"""AG-56: Autonomous Supervision Dashboard.

Consolidates AG-47 through AG-55 outputs into a unified supervisory
overview for the operator.

Dashboard-only — no governance mutation, no repair execution,
no baseline mutation, no auto-action on dashboard signals.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.dashboard_policy import (
    DASHBOARD_SECTIONS,
    sort_alerts_by_severity,
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


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_self_awareness(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-47 self-awareness artifacts."""
    rt = _rt(runtime_root)
    latest   = _read_json(Path(rt) / "state" / "runtime_self_awareness_latest.json") or {}
    readiness = _read_json(Path(rt) / "state" / "runtime_readiness.json") or {}
    return {
        "present":  bool(latest),
        "identity": latest.get("identity", {}),
        "posture":  latest.get("posture", {}),
        "readiness": readiness,
    }


def load_claim_trust(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-49 claim trust index."""
    rt = _rt(runtime_root)
    index  = _read_json(Path(rt) / "state" / "runtime_claim_trust_index.json") or {}
    latest = _read_json(Path(rt) / "state" / "runtime_claim_trust_latest.json") or {}
    return {
        "present":             bool(index),
        "overall_trust_score": index.get("overall_trust_score"),
        "overall_trust_class": index.get("overall_trust_class"),
        "gap_count":           index.get("gap_count", 0),
        "trust_gaps":          latest.get("trust_gaps", []),
    }


def load_trust_guidance(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-50 trust guidance."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_trust_guidance_latest.json") or {}
    return {
        "present":        bool(latest),
        "guidance_mode":  latest.get("guidance_mode"),
        "caution_class":  latest.get("caution_class"),
        "guidance_entries": latest.get("guidance_entries", []),
    }


def load_operator_confidence(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-51 operator confidence."""
    rt = _rt(runtime_root)
    index = _read_json(Path(rt) / "state" / "runtime_operator_confidence_index.json") or {}
    return {
        "present":             bool(index),
        "overall_confidence":  index.get("overall_confidence"),
        "confidence_class":    index.get("confidence_class"),
    }


def load_governance_gate(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-52 governance gate."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_governance_gate_latest.json") or {}
    return {
        "present":           bool(latest),
        "total_count":       latest.get("total_count", 0),
        "high_sensitivity":  latest.get("high_sensitivity", 0),
        "critical":          latest.get("critical", 0),
        "gated_recommendations": latest.get("gated_recommendations", []),
    }


def load_operator_integrity(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-53 operator decision flow integrity."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_operator_decision_integrity_latest.json") or {}
    return {
        "present":          bool(latest),
        "broken_chain":     latest.get("broken_chain", 0),
        "valid_lifecycle":  latest.get("valid_lifecycle", 0),
        "broken_results":   latest.get("broken_results", []),
    }


def load_governance_alerts(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-55 governance alerts."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_governance_alerts_latest.json") or {}
    return {
        "present":          bool(latest),
        "alert_count":      latest.get("alert_count", 0),
        "high_alert_count": latest.get("high_alert_count", 0),
        "severity_counts":  latest.get("severity_counts", {}),
        "alerts":           latest.get("alerts", []),
        "high_alerts":      latest.get("high_alerts", []),
    }


# ---------------------------------------------------------------------------
# Dashboard builder
# ---------------------------------------------------------------------------

def build_supervision_dashboard(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-56 supervision dashboard report."""
    rt = _rt(runtime_root)

    sa_data         = load_self_awareness(rt)
    trust_data      = load_claim_trust(rt)
    guidance_data   = load_trust_guidance(rt)
    confidence_data = load_operator_confidence(rt)
    gate_data       = load_governance_gate(rt)
    integrity_data  = load_operator_integrity(rt)
    alerts_data     = load_governance_alerts(rt)

    # Compose sections
    identity  = sa_data.get("identity", {})
    readiness = sa_data.get("readiness", {})
    posture   = sa_data.get("posture", {})

    top_trust_gaps    = trust_data.get("trust_gaps", [])[:3]
    top_guidance      = guidance_data.get("guidance_entries", [])[:3]
    high_alerts       = sort_alerts_by_severity(alerts_data.get("high_alerts", []))
    integrity_breaks  = integrity_data.get("broken_results", [])[:5]

    open_queue_summary = {
        "total_gated":       gate_data.get("total_count", 0),
        "high_sensitivity":  gate_data.get("high_sensitivity", 0),
        "critical":          gate_data.get("critical", 0),
        "broken_chains":     integrity_data.get("broken_chain", 0),
    }

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":      ts,
        "run_id":  str(uuid.uuid4()),
        "sections": DASHBOARD_SECTIONS,
        # ---- Section data ----
        "runtime_identity": identity,
        "readiness":        readiness,
        "posture":          posture,
        "trust_index": {
            "overall_trust_score": trust_data.get("overall_trust_score"),
            "overall_trust_class": trust_data.get("overall_trust_class"),
            "gap_count":           trust_data.get("gap_count", 0),
            "guidance_mode":       guidance_data.get("guidance_mode"),
            "caution_class":       guidance_data.get("caution_class"),
            "overall_confidence":  confidence_data.get("overall_confidence"),
            "confidence_class":    confidence_data.get("confidence_class"),
        },
        "top_trust_gaps":             top_trust_gaps,
        "top_guidance_items":         top_guidance,
        "open_decision_queue_summary": open_queue_summary,
        "governance_alerts":          high_alerts,
        "integrity_breaks":           integrity_breaks,
        # ---- Summary counters ----
        "alert_count":      alerts_data.get("alert_count", 0),
        "high_alert_count": alerts_data.get("high_alert_count", 0),
        "severity_counts":  alerts_data.get("severity_counts", {}),
        "evidence_refs": [
            "runtime_self_awareness_latest.json",
            "runtime_claim_trust_latest.json",
            "runtime_trust_guidance_latest.json",
            "runtime_operator_confidence_index.json",
            "runtime_governance_gate_latest.json",
            "runtime_operator_decision_integrity_latest.json",
            "runtime_governance_alerts_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_supervision_dashboard(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-56 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_supervision_dashboard_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_supervision_dashboard_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":               report["ts"],
        "run_id":           report["run_id"],
        "alert_count":      report["alert_count"],
        "high_alert_count": report["high_alert_count"],
        "severity_counts":  report["severity_counts"],
        "sections":         report["sections"],
    }
    _atomic_write(state_dir / "runtime_supervision_dashboard_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_supervision_dashboard(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-56 supervision dashboard and persist outputs."""
    try:
        report = build_supervision_dashboard(runtime_root)
        store_supervision_dashboard(report, runtime_root)
        return {
            "ok":               True,
            "alert_count":      report["alert_count"],
            "high_alert_count": report["high_alert_count"],
            "sections":         report["sections"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
