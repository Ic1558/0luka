"""AG-55: Governance Alert System.

Turns critical governance events, trust failures, claim mismatches,
and integrity breaks into operator-facing alerts.

Alert-only — no governance mutation, no execution, no baseline mutation,
no auto-escalation, no repair execution.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.governance_alert_policy import (
    ALERT_CLASSES,
    severity_for_alert_class,
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

def load_claim_trust_gaps(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-49 claim trust gaps."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_claim_trust_latest.json") or {}
    return {
        "present": bool(latest),
        "trust_gaps": latest.get("trust_gaps", []),
        "overall_trust_class": latest.get("overall_trust_class"),
        "overall_trust_score": latest.get("overall_trust_score"),
        "mismatches": latest.get("mismatches", []),
    }


def load_operator_integrity_results(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-53 operator decision flow integrity results."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_operator_decision_integrity_latest.json") or {}
    return {
        "present": bool(latest),
        "broken_chain": latest.get("broken_chain", 0),
        "broken_results": latest.get("broken_results", []),
        "valid_lifecycle": latest.get("valid_lifecycle", 0),
    }


def load_governance_gate_outputs(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-52 governance gate outputs."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_governance_gate_latest.json") or {}
    return {
        "present": bool(latest),
        "gated_recommendations": latest.get("gated_recommendations", []),
        "high_sensitivity": latest.get("high_sensitivity", 0),
        "critical": latest.get("critical", 0),
        "total_count": latest.get("total_count", 0),
    }


def load_recommendation_feedback(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-54 recommendation feedback."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_recommendation_feedback_latest.json") or {}
    return {
        "present": bool(latest),
        "gaps": latest.get("gaps", []),
        "feedback_counts": latest.get("feedback_counts", {}),
        "recommendations_total": latest.get("recommendations_total", 0),
    }


# ---------------------------------------------------------------------------
# Alert detection
# ---------------------------------------------------------------------------

def _make_alert(
    alert_class: str,
    title: str,
    description: str,
    evidence_refs: list[str],
    context: dict | None = None,
) -> dict[str, Any]:
    return {
        "alert_id":    str(uuid.uuid4()),
        "alert_class": alert_class,
        "severity":    severity_for_alert_class(alert_class),
        "title":       title,
        "description": description,
        "evidence_refs": evidence_refs,
        "context":     context or {},
    }


def detect_alert_conditions(
    trust_data: dict[str, Any],
    integrity_data: dict[str, Any],
    gate_data: dict[str, Any],
    feedback_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Detect all alert conditions and return alert list."""
    alerts: list[dict[str, Any]] = []

    # CLAIM_MISMATCH_ALERT — mismatches in trust data
    for mismatch in trust_data.get("mismatches", []):
        alerts.append(_make_alert(
            "CLAIM_MISMATCH_ALERT",
            f"Claim mismatch: {mismatch.get('claim_key', '?')}",
            f"Claimed '{mismatch.get('claimed_value')}' but observed '{mismatch.get('observed_value')}'.",
            ["runtime_claim_trust_latest.json"],
            {"mismatch": mismatch},
        ))

    # Also fire CLAIM_MISMATCH_ALERT when trust class is UNTRUSTED
    if trust_data.get("overall_trust_class") == "UNTRUSTED":
        alerts.append(_make_alert(
            "CLAIM_MISMATCH_ALERT",
            "Runtime trust class: UNTRUSTED",
            "Overall trust class is UNTRUSTED. Manual state inspection required.",
            ["runtime_claim_trust_latest.json"],
        ))

    # GOVERNANCE_INTEGRITY_BREAK — broken lifecycle chains
    broken = integrity_data.get("broken_chain", 0)
    if broken > 0:
        for br in integrity_data.get("broken_results", [])[:5]:
            alerts.append(_make_alert(
                "GOVERNANCE_INTEGRITY_BREAK",
                f"Broken lifecycle chain: {br.get('recommendation_id', '?')}",
                f"Missing steps: {br.get('missing_steps', [])}",
                ["runtime_operator_decision_integrity_latest.json"],
                {"broken_result": br},
            ))

    # HIGH_SENSITIVITY_RECOMMENDATION_ALERT
    hs_count = gate_data.get("high_sensitivity", 0)
    crit_count = gate_data.get("critical", 0)
    if hs_count > 0 or crit_count > 0:
        alerts.append(_make_alert(
            "HIGH_SENSITIVITY_RECOMMENDATION_ALERT",
            f"High-sensitivity recommendations: {hs_count + crit_count}",
            f"{hs_count} HIGH_SENSITIVITY + {crit_count} CRITICAL_GOVERNANCE recommendations pending operator review.",
            ["runtime_governance_gate_latest.json"],
            {"high_sensitivity": hs_count, "critical": crit_count},
        ))

    # TRUST_GAP_ALERT
    for gap in trust_data.get("trust_gaps", [])[:3]:
        if gap.get("severity") in ("HIGH", "CRITICAL"):
            alerts.append(_make_alert(
                "TRUST_GAP_ALERT",
                f"Trust gap: {gap.get('gap_type', '?')}",
                gap.get("summary", ""),
                ["runtime_claim_trust_latest.json"],
                {"gap": gap},
            ))

    # FEEDBACK_DIVERGENCE_ALERT — ignored or overridden recommendations
    for gap_entry in feedback_data.get("gaps", []):
        fc = gap_entry.get("feedback_class", "")
        if fc in ("IGNORED", "OVERRIDDEN"):
            alerts.append(_make_alert(
                "FEEDBACK_DIVERGENCE_ALERT",
                f"Feedback divergence: {gap_entry.get('recommendation_id', '?')} → {fc}",
                gap_entry.get("summary", ""),
                ["runtime_recommendation_feedback_latest.json"],
                {"feedback_entry": gap_entry},
            ))

    return sort_alerts_by_severity(alerts)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_governance_alert_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-55 governance alert report."""
    rt = _rt(runtime_root)

    trust_data     = load_claim_trust_gaps(rt)
    integrity_data = load_operator_integrity_results(rt)
    gate_data      = load_governance_gate_outputs(rt)
    feedback_data  = load_recommendation_feedback(rt)

    alerts = detect_alert_conditions(trust_data, integrity_data, gate_data, feedback_data)

    high_alerts = [a for a in alerts if a["severity"] in ("HIGH", "CRITICAL")]

    severity_counts: dict[str, int] = {"INFO": 0, "WARNING": 0, "HIGH": 0, "CRITICAL": 0}
    for a in alerts:
        sev = a.get("severity", "INFO")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":              ts,
        "run_id":          str(uuid.uuid4()),
        "alert_count":     len(alerts),
        "high_alert_count": len(high_alerts),
        "severity_counts": severity_counts,
        "alerts":          alerts,
        "high_alerts":     high_alerts,
        "evidence_refs": [
            "runtime_claim_trust_latest.json",
            "runtime_operator_decision_integrity_latest.json",
            "runtime_governance_gate_latest.json",
            "runtime_recommendation_feedback_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_governance_alerts(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-55 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_governance_alerts_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_governance_alerts_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":               report["ts"],
        "run_id":           report["run_id"],
        "alert_count":      report["alert_count"],
        "high_alert_count": report["high_alert_count"],
        "severity_counts":  report["severity_counts"],
    }
    _atomic_write(state_dir / "runtime_governance_alerts_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_governance_alerts(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-55 governance alert detection and persist outputs."""
    try:
        report = build_governance_alert_report(runtime_root)
        store_governance_alerts(report, runtime_root)
        return {
            "ok":               True,
            "alert_count":      report["alert_count"],
            "high_alert_count": report["high_alert_count"],
            "severity_counts":  report["severity_counts"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
