"""AG-51: Operator Confidence Calibration.

Synthesises trust index, trust guidance, claim verification and self-awareness
artifacts into a calibrated operator confidence report.

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

from runtime.operator_confidence_policy import (
    CALIBRATION_DIMENSIONS,
    WEIGHT_BY_DIMENSION,
    classify_confidence,
    calibrate_dimension,
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

def load_trust_index(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-49 claim trust index."""
    rt = _rt(runtime_root)
    index  = _read_json(Path(rt) / "state" / "runtime_claim_trust_index.json") or {}
    latest = _read_json(Path(rt) / "state" / "runtime_claim_trust_latest.json") or {}
    return {
        "index":               index,
        "latest":              latest,
        "overall_trust_score": index.get("overall_trust_score"),
        "overall_trust_class": index.get("overall_trust_class"),
        "gap_count":           index.get("gap_count", 0),
        "trust_gaps":          latest.get("trust_gaps", []),
        "present":             bool(index),
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
        "entry_count":         index.get("entry_count", 0),
        "present":             bool(index),
    }


def load_claim_verification(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-48 claim verification results."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_claim_verification_latest.json") or {}
    return {
        "latest":     latest,
        "mismatches": latest.get("mismatches", []),
        "all_results": latest.get("all_results", []),
        "present":    bool(latest),
    }


def load_self_awareness(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-47 self-awareness artifacts."""
    rt = _rt(runtime_root)
    latest    = _read_json(Path(rt) / "state" / "runtime_self_awareness_latest.json") or {}
    readiness = _read_json(Path(rt) / "state" / "runtime_readiness.json") or {}
    return {
        "latest":    latest,
        "readiness": readiness,
        "identity":  latest.get("identity", {}),
        "posture":   latest.get("posture", {}),
        "present":   bool(latest),
    }


# ---------------------------------------------------------------------------
# Calibrators
# ---------------------------------------------------------------------------

def calibrate_trust_alignment(trust_data: dict[str, Any]) -> dict[str, Any]:
    """Calibrate the trust_alignment dimension."""
    trust_score = float(trust_data.get("overall_trust_score") or 0.0)
    gap_count   = int(trust_data.get("gap_count", 0))

    # Penalise for gaps
    penalty = min(0.05 * gap_count, 0.30)
    score   = max(0.0, trust_score - penalty)

    rationale = (
        f"Trust score {trust_score:.2f} with {gap_count} gap(s). "
        f"Adjusted score after gap penalty: {score:.2f}."
    )
    return calibrate_dimension(
        "trust_alignment",
        {"score": score, "rationale": rationale},
    )


def calibrate_gap_severity(trust_data: dict[str, Any]) -> dict[str, Any]:
    """Calibrate the gap_severity dimension."""
    gaps      = trust_data.get("trust_gaps", [])
    gap_count = int(trust_data.get("gap_count", 0))

    high_severity = sum(1 for g in gaps if g.get("severity") == "HIGH")
    if gap_count == 0:
        score = 1.0
        rationale = "No trust gaps detected."
    else:
        # Each HIGH gap costs 0.20; each other gap costs 0.10
        penalty = (high_severity * 0.20) + ((gap_count - high_severity) * 0.10)
        score   = max(0.0, 1.0 - penalty)
        rationale = (
            f"{gap_count} gap(s) found ({high_severity} HIGH). "
            f"Severity penalty: {penalty:.2f}."
        )
    return calibrate_dimension(
        "gap_severity",
        {"score": score, "rationale": rationale},
    )


def calibrate_claim_consistency(verification_data: dict[str, Any]) -> dict[str, Any]:
    """Calibrate the claim_consistency dimension."""
    mismatches  = verification_data.get("mismatches", [])
    all_results = verification_data.get("all_results", [])
    total       = max(len(all_results), 1)
    mismatch_count = len(mismatches)

    score     = max(0.0, 1.0 - (mismatch_count / total) - (mismatch_count * 0.05))
    rationale = (
        f"{mismatch_count} mismatch(es) out of {total} claim result(s). "
        f"Consistency score: {score:.2f}."
    )
    return calibrate_dimension(
        "claim_consistency",
        {"score": score, "rationale": rationale},
    )


def calibrate_readiness_match(self_awareness: dict[str, Any]) -> dict[str, Any]:
    """Calibrate the readiness_match dimension."""
    readiness = self_awareness.get("readiness", {})
    level     = str(readiness.get("readiness") or readiness.get("level") or "").upper()

    readiness_score_map = {
        "READY":             1.0,
        "LIMITED":           0.55,
        "DEGRADED":          0.30,
        "NOT_READY":         0.10,
        "UNAVAILABLE":       0.05,
        "":                  0.50,   # unknown — neutral
    }
    score     = readiness_score_map.get(level, 0.50)
    rationale = f"Readiness level: {level or 'UNKNOWN'}. Score: {score:.2f}."
    return calibrate_dimension(
        "readiness_match",
        {"score": score, "rationale": rationale},
    )


def calibrate_posture_alignment(
    self_awareness: dict[str, Any],
    verification_data: dict[str, Any],
) -> dict[str, Any]:
    """Calibrate the posture_alignment dimension."""
    posture = self_awareness.get("posture", {})
    declared_posture = str(
        posture.get("posture_class") or posture.get("posture") or ""
    ).upper()

    mismatches = verification_data.get("mismatches", [])
    posture_mismatches = [
        m for m in mismatches
        if "posture" in str(m.get("claim_key", "")).lower()
    ]

    if not declared_posture:
        score     = 0.50
        rationale = "Posture undeclared — neutral score."
    elif posture_mismatches:
        score     = 0.20
        rationale = (
            f"Declared posture '{declared_posture}' has {len(posture_mismatches)} "
            f"mismatch(es) in verification data."
        )
    else:
        score     = 0.90
        rationale = (
            f"Declared posture '{declared_posture}' has no observed mismatches."
        )
    return calibrate_dimension(
        "posture_alignment",
        {"score": score, "rationale": rationale},
    )


# ---------------------------------------------------------------------------
# Overall confidence
# ---------------------------------------------------------------------------

def derive_overall_confidence(calibrations: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive an overall confidence score and class from dimension calibrations.

    Uses WEIGHT_BY_DIMENSION for weighted average.
    Returns:
        {
            "overall_confidence_score": float,
            "overall_confidence_class": str,
            "rationale":                str,
        }
    """
    if not calibrations:
        return {
            "overall_confidence_score": 0.0,
            "overall_confidence_class": classify_confidence(0.0),
            "rationale":               "No calibration data available.",
        }

    by_dim = {c["dimension"]: c["score"] for c in calibrations}
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, weight in WEIGHT_BY_DIMENSION.items():
        score = by_dim.get(dim, 0.5)   # default to 0.5 if dimension missing
        weighted_sum += score * weight
        total_weight += weight

    overall = weighted_sum / total_weight if total_weight > 0 else 0.0
    overall = max(0.0, min(1.0, overall))
    return {
        "overall_confidence_score": round(overall, 4),
        "overall_confidence_class": classify_confidence(overall),
        "rationale": (
            f"Weighted average of {len(calibrations)} dimension(s). "
            f"Total weight: {total_weight:.2f}. Score: {overall:.4f}."
        ),
    }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_confidence_calibration_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-51 operator confidence calibration report."""
    rt = _rt(runtime_root)

    trust_data        = load_trust_index(rt)
    _trust_guidance   = load_trust_guidance(rt)
    verification_data = load_claim_verification(rt)
    self_awareness    = load_self_awareness(rt)

    calibrations = [
        calibrate_trust_alignment(trust_data),
        calibrate_gap_severity(trust_data),
        calibrate_claim_consistency(verification_data),
        calibrate_readiness_match(self_awareness),
        calibrate_posture_alignment(self_awareness, verification_data),
    ]

    overall = derive_overall_confidence(calibrations)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                     ts,
        "run_id":                 str(uuid.uuid4()),
        "overall_confidence_score": overall["overall_confidence_score"],
        "overall_confidence_class": overall["overall_confidence_class"],
        "calibrations":           calibrations,
        "evidence_refs": [
            "runtime_claim_trust_index.json",
            "runtime_claim_trust_latest.json",
            "runtime_trust_guidance_index.json",
            "runtime_self_awareness_latest.json",
            "runtime_claim_verification_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_confidence_calibration(
    report: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Persist AG-51 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_operator_confidence_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_operator_confidence_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":                     report["ts"],
        "run_id":                 report["run_id"],
        "overall_confidence_score": report["overall_confidence_score"],
        "overall_confidence_class": report["overall_confidence_class"],
        "dimension_count":        len(report["calibrations"]),
    }
    _atomic_write(state_dir / "runtime_operator_confidence_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_operator_confidence_calibration(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-51 operator confidence calibration and persist outputs."""
    try:
        report = build_confidence_calibration_report(runtime_root)
        store_confidence_calibration(report, runtime_root)
        return {
            "ok":                     True,
            "overall_confidence_score": report["overall_confidence_score"],
            "overall_confidence_class": report["overall_confidence_class"],
            "dimension_count":        len(report["calibrations"]),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
