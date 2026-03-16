"""AG-52: Runtime Recommendation Governance Gate.

Classifies each guidance/recommendation entry with a governance sensitivity
class and attaches a review gate so the operator can decide what to act on.

Advisory-only — no governance mutation, no campaign mutation,
no repair execution, no baseline mutation, no automatic claim correction.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.governance_gate_policy import (
    GOVERNANCE_CLASSES,
    GOVERNANCE_CLASS_TO_REVIEW_LEVEL,
    classify_governance_class,
    requires_governance_review,
    requires_operator_review,
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

def load_runtime_recommendations(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-50 guidance entries (they serve as recommendations)."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_trust_guidance_latest.json") or {}
    entries = latest.get("guidance_entries", [])
    return {
        "entries": entries,
        "entry_count": len(entries),
        "present": bool(latest),
    }


def load_trust_guidance(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-50 trust guidance index."""
    rt = _rt(runtime_root)
    index = _read_json(Path(rt) / "state" / "runtime_trust_guidance_index.json") or {}
    return {
        "index":               index,
        "guidance_mode":       index.get("guidance_mode"),
        "caution_class":       index.get("caution_class"),
        "overall_trust_score": index.get("overall_trust_score"),
        "overall_trust_class": index.get("overall_trust_class"),
        "gap_count":           index.get("gap_count", 0),
        "present":             bool(index),
    }


def load_operator_confidence(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-51 operator confidence index."""
    rt = _rt(runtime_root)
    index = _read_json(Path(rt) / "state" / "runtime_operator_confidence_index.json") or {}
    return {
        "index":                   index,
        "overall_confidence_score": index.get("overall_confidence_score"),
        "overall_confidence_class": index.get("overall_confidence_class"),
        "present":                 bool(index),
    }


def load_decision_queue_context(runtime_root: str | None = None) -> dict[str, Any]:
    """Load decision queue governance context (read-only)."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json") or {}
    return {
        "latest":      latest,
        "open_count":  latest.get("open_count", 0),
        "present":     bool(latest),
    }


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

def classify_governance_sensitivity(
    rec: dict[str, Any],
    trust_data: dict[str, Any],
    confidence_data: dict[str, Any],
) -> str:
    """Classify a single recommendation's governance sensitivity."""
    trust_class      = trust_data.get("overall_trust_class") or ""
    confidence_class = confidence_data.get("overall_confidence_class") or ""
    gap_count        = int(trust_data.get("gap_count", 0))

    # Individual recommendation overrides
    if rec.get("caution_class") == "CRITICAL_CAUTION":
        return "CRITICAL_GOVERNANCE"
    if rec.get("guidance_mode") == "CLAIM_MISMATCH_ALERT":
        return "CRITICAL_GOVERNANCE"
    if rec.get("caution_class") in ("HIGH_CAUTION",):
        return "HIGH_SENSITIVITY"

    return classify_governance_class(trust_class, confidence_class, gap_count)


def attach_governance_gate(
    rec: dict[str, Any],
    governance_class: str,
    trust_data: dict[str, Any],
    confidence_data: dict[str, Any],
) -> dict[str, Any]:
    """Attach governance gate metadata to a recommendation."""
    review_level = GOVERNANCE_CLASS_TO_REVIEW_LEVEL.get(governance_class, "STANDARD_REVIEW")
    return {
        "recommendation_id":     rec.get("guidance_id", f"rec-{uuid.uuid4().hex[:6]}"),
        "target_ref":            rec.get("guidance_id", "guidance-unknown"),
        "governance_class":      governance_class,
        "requires_operator_review": requires_operator_review(governance_class),
        "recommended_review_level": review_level,
        "confidence_class":      confidence_data.get("overall_confidence_class"),
        "trust_class":           trust_data.get("overall_trust_class"),
        "evidence_refs": [
            "runtime_claim_trust_latest.json",
            "runtime_operator_confidence_latest.json",
        ],
    }


def generate_governance_gated_recommendations(
    recs: list[dict[str, Any]],
    trust_data: dict[str, Any],
    confidence_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Classify and gate all recommendations."""
    gated: list[dict[str, Any]] = []
    for rec in recs:
        gov_class = classify_governance_sensitivity(rec, trust_data, confidence_data)
        gate      = attach_governance_gate(rec, gov_class, trust_data, confidence_data)
        gated.append(gate)
    return gated


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_governance_gate_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-52 governance gate report."""
    rt = _rt(runtime_root)

    rec_data        = load_runtime_recommendations(rt)
    trust_data      = load_trust_guidance(rt)
    confidence_data = load_operator_confidence(rt)
    _dq_ctx         = load_decision_queue_context(rt)  # read-only context

    gated = generate_governance_gated_recommendations(
        rec_data["entries"], trust_data, confidence_data
    )

    # Counts per governance class
    gov_summary: dict[str, int] = {cls: 0 for cls in GOVERNANCE_CLASSES}
    for g in gated:
        gc = g.get("governance_class", "MEDIUM_SENSITIVITY")
        gov_summary[gc] = gov_summary.get(gc, 0) + 1

    high_sensitivity = gov_summary.get("HIGH_SENSITIVITY", 0)
    critical         = gov_summary.get("CRITICAL_GOVERNANCE", 0)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                    ts,
        "run_id":                str(uuid.uuid4()),
        "gated_recommendations": gated,
        "total_count":           len(gated),
        "high_sensitivity":      high_sensitivity,
        "critical":              critical,
        "governance_summary":    gov_summary,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_governance_gate_outputs(
    report: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Persist AG-52 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_governance_gate_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_governance_gate_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":                report["ts"],
        "run_id":            report["run_id"],
        "total_count":       report["total_count"],
        "high_sensitivity":  report["high_sensitivity"],
        "critical":          report["critical"],
        "governance_summary": report["governance_summary"],
    }
    _atomic_write(state_dir / "runtime_governance_gate_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_recommendation_governance_gate(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-52 governance gate and persist outputs."""
    try:
        report = build_governance_gate_report(runtime_root)
        store_governance_gate_outputs(report, runtime_root)
        return {
            "ok":              True,
            "total_count":     report["total_count"],
            "high_sensitivity": report["high_sensitivity"],
            "critical":        report["critical"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
