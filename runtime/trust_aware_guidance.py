"""AG-50: Runtime Trust-Aware Operator Guidance.

Synthesises AG-49 trust index + AG-47 self-awareness into operator-facing
guidance entries that reflect the current trust posture of the runtime.

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

from runtime.trust_guidance_policy import (
    GUIDANCE_MODES,
    classify_caution,
    guidance_description,
    guidance_mode_for_trust_class,
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
    latest = _read_json(Path(rt) / "state" / "runtime_claim_trust_latest.json") or {}
    index  = _read_json(Path(rt) / "state" / "runtime_claim_trust_index.json") or {}
    return {
        "latest":              latest,
        "index":               index,
        "overall_trust_score": index.get("overall_trust_score"),
        "overall_trust_class": index.get("overall_trust_class"),
        "gap_count":           index.get("gap_count", 0),
        "top_gap":             index.get("top_gap"),
        "trust_gaps":          latest.get("trust_gaps", []),
        "present":             bool(index),
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
    }


def load_claim_verification(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-48 claim verification results."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_claim_verification_latest.json") or {}
    return {
        "latest":     latest,
        "mismatches": latest.get("mismatches", []),
        "present":    bool(latest),
    }


# ---------------------------------------------------------------------------
# Guidance builders
# ---------------------------------------------------------------------------

def derive_guidance_mode(trust_data: dict[str, Any]) -> str:
    """Derive guidance mode from trust index data."""
    trust_class = trust_data.get("overall_trust_class")
    if not trust_class:
        return "CLAIM_MISMATCH_ALERT"
    return guidance_mode_for_trust_class(trust_class)


def build_guidance_entries(
    trust_data: dict[str, Any],
    self_awareness: dict[str, Any],
    verification_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build per-dimension guidance entries for the operator."""
    entries: list[dict[str, Any]] = []
    overall_mode = derive_guidance_mode(trust_data)
    trust_score  = trust_data.get("overall_trust_score") or 0.0
    gap_count    = trust_data.get("gap_count", 0)
    caution      = classify_caution(trust_score, gap_count)

    # Overall guidance entry
    entries.append({
        "guidance_id":      "guidance-overall",
        "dimension":        "overall",
        "guidance_mode":    overall_mode,
        "caution_class":    caution,
        "trust_score":      trust_score,
        "trust_class":      trust_data.get("overall_trust_class"),
        "description":      guidance_description(overall_mode),
        "evidence_refs":    ["runtime_claim_trust_index.json"],
        "override_type":    "NO_OVERRIDE",
    })

    # Gap-specific guidance entries (top 3 gaps)
    for i, gap in enumerate(trust_data.get("trust_gaps", [])[:3]):
        entries.append({
            "guidance_id":   f"guidance-gap-{i+1:03d}",
            "dimension":     "gap",
            "guidance_mode": "HIGH_SCRUTINY" if gap.get("severity") == "HIGH" else overall_mode,
            "caution_class": "HIGH_CAUTION" if gap.get("severity") == "HIGH" else caution,
            "gap_type":      gap.get("gap_type"),
            "gap_severity":  gap.get("severity"),
            "summary":       gap.get("summary", ""),
            "evidence_refs": gap.get("evidence_refs", []),
            "override_type": "GAP_SEVERITY_OVERRIDE" if gap.get("severity") == "HIGH" else "NO_OVERRIDE",
        })

    # Mismatch alert entries
    for mismatch in verification_data.get("mismatches", [])[:2]:
        entries.append({
            "guidance_id":   f"guidance-mismatch-{mismatch.get('claim_key','?')}",
            "dimension":     "mismatch",
            "guidance_mode": "CLAIM_MISMATCH_ALERT",
            "caution_class": "CRITICAL_CAUTION",
            "claim_key":     mismatch.get("claim_key"),
            "claimed_value": mismatch.get("claimed_value"),
            "observed_value": mismatch.get("observed_value"),
            "description":   guidance_description("CLAIM_MISMATCH_ALERT"),
            "evidence_refs": ["runtime_claim_verification_latest.json"],
            "override_type": "CLAIM_MISMATCH_OVERRIDE",
        })

    return entries


def build_trust_guidance_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-50 trust-aware operator guidance report."""
    rt = _rt(runtime_root)

    trust_data        = load_trust_index(rt)
    self_awareness    = load_self_awareness(rt)
    verification_data = load_claim_verification(rt)

    guidance_mode   = derive_guidance_mode(trust_data)
    trust_score     = trust_data.get("overall_trust_score") or 0.0
    gap_count       = trust_data.get("gap_count", 0)
    caution_class   = classify_caution(trust_score, gap_count)
    guidance_entries = build_guidance_entries(trust_data, self_awareness, verification_data)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":               ts,
        "run_id":           str(uuid.uuid4()),
        "guidance_mode":    guidance_mode,
        "caution_class":    caution_class,
        "overall_trust_score": trust_score,
        "overall_trust_class": trust_data.get("overall_trust_class"),
        "gap_count":        gap_count,
        "guidance_entries": guidance_entries,
        "description":      guidance_description(guidance_mode),
        "evidence_refs": [
            "runtime_claim_trust_index.json",
            "runtime_claim_trust_latest.json",
            "runtime_self_awareness_latest.json",
            "runtime_claim_verification_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_trust_guidance(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-50 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_trust_guidance_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_trust_guidance_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":               report["ts"],
        "run_id":           report["run_id"],
        "guidance_mode":    report["guidance_mode"],
        "caution_class":    report["caution_class"],
        "overall_trust_score": report["overall_trust_score"],
        "overall_trust_class": report["overall_trust_class"],
        "gap_count":        report["gap_count"],
        "entry_count":      len(report["guidance_entries"]),
    }
    _atomic_write(state_dir / "runtime_trust_guidance_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_trust_aware_guidance(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-50 trust-aware guidance and persist outputs."""
    try:
        report = build_trust_guidance_report(runtime_root)
        store_trust_guidance(report, runtime_root)
        return {
            "ok":               True,
            "guidance_mode":    report["guidance_mode"],
            "caution_class":    report["caution_class"],
            "overall_trust_score": report["overall_trust_score"],
            "overall_trust_class": report["overall_trust_class"],
            "entry_count":      len(report["guidance_entries"]),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
