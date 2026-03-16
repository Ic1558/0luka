"""AG-49: Runtime Claim Trust Index Layer.

Synthesizes AG-48 claim verification results into operator-facing
trust scores, trust classes, and trust-gap summaries.

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

from runtime.claim_trust_policy import (
    CLAIM_GROUP_WEIGHTS,
    GAP_SEVERITY,
    classify_trust,
    weighted_claim_group_score,
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


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except Exception:
            continue
    return rows


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_claim_verification(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-48 claim verification outputs."""
    rt = _rt(runtime_root)
    latest   = _read_json(Path(rt) / "state" / "runtime_claim_verification_latest.json") or {}
    verdicts = _read_json(Path(rt) / "state" / "runtime_claim_verdicts.json") or {}
    return {
        "latest":   latest,
        "verdicts": verdicts,
        "all_results":        latest.get("all_results", []),
        "identity_results":   latest.get("identity_results", []),
        "readiness_results":  latest.get("readiness_results", []),
        "posture_results":    latest.get("posture_results", []),
        "mismatches":         latest.get("mismatches", []),
        "present":            bool(latest),
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


def load_capability_envelope(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-46 capability state."""
    rt = _rt(runtime_root)
    try:
        from runtime.capability_registry import list_active_capabilities, registry_summary
        active  = list_active_capabilities(rt)
        summary = registry_summary(rt)
    except Exception:
        active  = []
        summary = {"total_registered": 0, "active_count": 0}
    return {"active_capabilities": active, "active_count": len(active), "summary": summary}


# ---------------------------------------------------------------------------
# Trust scoring functions
# ---------------------------------------------------------------------------

def _count_verdicts(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"VERIFIED": 0, "INCONSISTENT": 0, "UNSUPPORTED": 0, "INCONCLUSIVE": 0}
    for r in results:
        v = r.get("verdict", "INCONCLUSIVE")
        counts[v] = counts.get(v, 0) + 1
    return counts


def score_identity_trust(verification_data: dict[str, Any]) -> dict[str, Any]:
    """Score identity claim trust from AG-48 verdicts."""
    results = verification_data.get("identity_results", [])
    counts  = _count_verdicts(results)
    score   = weighted_claim_group_score(
        counts["VERIFIED"], counts["INCONSISTENT"], counts["UNSUPPORTED"], counts["INCONCLUSIVE"]
    )
    return {
        "claim_group":  "identity",
        "trust_score":  score,
        "trust_class":  classify_trust(score),
        "verified":     counts["VERIFIED"],
        "inconsistent": counts["INCONSISTENT"],
        "unsupported":  counts["UNSUPPORTED"],
        "inconclusive": counts["INCONCLUSIVE"],
        "total":        len(results),
    }


def score_readiness_trust(verification_data: dict[str, Any]) -> dict[str, Any]:
    """Score readiness claim trust from AG-48 verdicts."""
    results = verification_data.get("readiness_results", [])
    counts  = _count_verdicts(results)
    score   = weighted_claim_group_score(
        counts["VERIFIED"], counts["INCONSISTENT"], counts["UNSUPPORTED"], counts["INCONCLUSIVE"]
    )
    return {
        "claim_group":  "readiness",
        "trust_score":  score,
        "trust_class":  classify_trust(score),
        "verified":     counts["VERIFIED"],
        "inconsistent": counts["INCONSISTENT"],
        "unsupported":  counts["UNSUPPORTED"],
        "inconclusive": counts["INCONCLUSIVE"],
        "total":        len(results),
    }


def score_posture_trust(verification_data: dict[str, Any]) -> dict[str, Any]:
    """Score posture claim trust from AG-48 verdicts."""
    results = verification_data.get("posture_results", [])
    counts  = _count_verdicts(results)
    score   = weighted_claim_group_score(
        counts["VERIFIED"], counts["INCONSISTENT"], counts["UNSUPPORTED"], counts["INCONCLUSIVE"]
    )
    return {
        "claim_group":  "posture",
        "trust_score":  score,
        "trust_class":  classify_trust(score),
        "verified":     counts["VERIFIED"],
        "inconsistent": counts["INCONSISTENT"],
        "unsupported":  counts["UNSUPPORTED"],
        "inconclusive": counts["INCONCLUSIVE"],
        "total":        len(results),
    }


# ---------------------------------------------------------------------------
# Overall trust index
# ---------------------------------------------------------------------------

def derive_overall_trust_index(
    identity_trust: dict[str, Any],
    readiness_trust: dict[str, Any],
    posture_trust: dict[str, Any],
) -> dict[str, Any]:
    """Combine group scores into overall trust index using configured weights."""
    w = CLAIM_GROUP_WEIGHTS
    overall_score = round(
        identity_trust["trust_score"]  * w["identity"]
        + readiness_trust["trust_score"] * w["readiness"]
        + posture_trust["trust_score"]   * w["posture"],
        4,
    )
    return {
        "overall_trust_score": overall_score,
        "overall_trust_class": classify_trust(overall_score),
        "claim_groups": {
            "identity":  identity_trust["trust_class"],
            "readiness": readiness_trust["trust_class"],
            "posture":   posture_trust["trust_class"],
        },
        "group_scores": {
            "identity":  identity_trust["trust_score"],
            "readiness": readiness_trust["trust_score"],
            "posture":   posture_trust["trust_score"],
        },
    }


# ---------------------------------------------------------------------------
# Trust gap summarisation
# ---------------------------------------------------------------------------

def summarize_trust_gaps(
    verification_data: dict[str, Any],
    self_awareness: dict[str, Any],
    capability_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Produce operator-facing trust gap entries."""
    gaps: list[dict[str, Any]] = []
    all_results = verification_data.get("all_results", [])
    gap_seq = 1

    def _gap(gap_type: str, summary: str, evidence_refs: list[str]) -> dict[str, Any]:
        nonlocal gap_seq
        entry = {
            "gap_id":      f"gap-{gap_seq:03d}",
            "gap_type":    gap_type,
            "severity":    GAP_SEVERITY.get(gap_type, "MEDIUM"),
            "summary":     summary,
            "evidence_refs": evidence_refs,
        }
        gap_seq += 1
        return entry

    for result in all_results:
        verdict  = result.get("verdict")
        ck       = result.get("claim_key", "")
        claimed  = result.get("claimed_value")
        observed = result.get("observed_value")

        if verdict == "INCONSISTENT":
            # Classify gap type
            if ck == "active_capability_count":
                gaps.append(_gap(
                    "capability_count_mismatch",
                    f"active_capability_count claimed={claimed} but envelope shows {observed}.",
                    ["runtime_capabilities.jsonl", "runtime_claim_verification_latest.json"],
                ))
            elif ck == "readiness":
                gaps.append(_gap(
                    "readiness_overclaim",
                    f"Readiness claimed={claimed!r} is not supported by current evidence.",
                    ["runtime_claim_verification_latest.json", "runtime_readiness.json"],
                ))
            elif ck == "operating_mode":
                gaps.append(_gap(
                    "inconsistent_operating_mode",
                    f"operating_mode claimed={claimed!r} but strategy shows {observed!r}.",
                    ["runtime_operating_mode.json", "runtime_claim_verification_latest.json"],
                ))
            else:
                gaps.append(_gap(
                    "posture_mismatch",
                    f"{ck}: claimed={claimed!r} contradicts evidence.",
                    ["runtime_claim_verification_latest.json"],
                ))

        elif verdict == "UNSUPPORTED":
            gaps.append(_gap(
                "unsupported_claim_dependency",
                f"{ck}: no supporting evidence found for claimed value {claimed!r}.",
                ["runtime_claim_verification_latest.json"],
            ))

    return gaps


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_claim_trust_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-49 claim trust index report."""
    rt = _rt(runtime_root)

    verification_data = load_claim_verification(rt)
    self_awareness    = load_self_awareness(rt)
    capability_data   = load_capability_envelope(rt)

    identity_trust  = score_identity_trust(verification_data)
    readiness_trust = score_readiness_trust(verification_data)
    posture_trust   = score_posture_trust(verification_data)

    overall = derive_overall_trust_index(identity_trust, readiness_trust, posture_trust)
    gaps    = summarize_trust_gaps(verification_data, self_awareness, capability_data)

    # Operator caution note based on overall trust class
    caution_notes = _operator_caution_notes(overall["overall_trust_class"], gaps)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":              ts,
        "run_id":          str(uuid.uuid4()),
        "identity_trust":  identity_trust,
        "readiness_trust": readiness_trust,
        "posture_trust":   posture_trust,
        "overall":         overall,
        "trust_gaps":      gaps,
        "caution_notes":   caution_notes,
        "evidence_refs": [
            "runtime_claim_verification_latest.json",
            "runtime_claim_verdicts.json",
            "runtime_self_awareness_latest.json",
            "runtime_capabilities.jsonl",
        ],
    }


def _operator_caution_notes(trust_class: str, gaps: list[dict]) -> list[str]:
    notes: list[str] = []
    if trust_class == "HIGH_TRUST":
        notes.append("Runtime claims are well-supported by evidence. Standard operator review applies.")
    elif trust_class == "TRUSTED_WITH_GAPS":
        notes.append("Runtime claims are mostly supported. Review identified gaps before acting on affected claims.")
    elif trust_class == "CAUTION":
        notes.append("Trust gaps detected. Treat runtime claims with caution; verify before relying on readiness or posture.")
    elif trust_class == "LOW_TRUST":
        notes.append("Multiple unsupported or inconsistent claims. Use manual verification before trusting runtime state.")
    else:
        notes.append("Runtime claims cannot be trusted. Operator should perform manual state inspection.")
    for g in gaps[:3]:
        notes.append(f"Gap: {g['gap_type']} — {g['summary']}")
    return notes


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_claim_trust(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-49 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_claim_trust_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    latest_path = state_dir / "runtime_claim_trust_latest.json"
    _atomic_write(latest_path, report)

    # 3. Slim index (atomic)
    index = {
        "ts":                  report["ts"],
        "run_id":              report["run_id"],
        "overall_trust_score": report["overall"]["overall_trust_score"],
        "overall_trust_class": report["overall"]["overall_trust_class"],
        "claim_groups":        report["overall"]["claim_groups"],
        "gap_count":           len(report["trust_gaps"]),
        "top_gap":             report["trust_gaps"][0]["gap_type"] if report["trust_gaps"] else None,
    }
    index_path = state_dir / "runtime_claim_trust_index.json"
    _atomic_write(index_path, index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_claim_trust_index(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-49 claim trust index and persist outputs."""
    try:
        report = build_claim_trust_report(runtime_root)
        store_claim_trust(report, runtime_root)
        return {
            "ok":                  True,
            "overall_trust_score": report["overall"]["overall_trust_score"],
            "overall_trust_class": report["overall"]["overall_trust_class"],
            "gap_count":           len(report["trust_gaps"]),
            "top_gap":             report["trust_gaps"][0]["gap_type"] if report["trust_gaps"] else None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
