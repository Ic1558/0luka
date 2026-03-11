from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tools.ops.control_plane_auto_lane_queue import load_auto_lane_candidate_contexts
from tools.ops.control_plane_auto_lane_review import (
    ALLOWED_ALIGNMENT_THRESHOLDS,
    ALLOWED_CONFIDENCE_REQUIREMENTS,
    BASELINE_ALIGNMENT_THRESHOLD,
    BASELINE_CONFIDENCE_REQUIREMENT,
    derive_auto_lane_review,
)
from tools.ops.control_plane_auto_lane_trends import DEFAULT_RECENT_CASES, derive_auto_lane_readiness_summary
from tools.ops.control_plane_policy_observability import load_policy_stats


def _normalize_alignment_threshold(value: Any) -> int:
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError as exc:
            raise ValueError("invalid_alignment_threshold") from exc
    if isinstance(value, bool) or not isinstance(value, int) or value not in ALLOWED_ALIGNMENT_THRESHOLDS:
        raise ValueError("invalid_alignment_threshold")
    return value


def _normalize_confidence_requirement(value: Any) -> str:
    if value is None:
        return BASELINE_CONFIDENCE_REQUIREMENT
    if not isinstance(value, str):
        raise ValueError("invalid_confidence_requirement")
    normalized = value.strip().upper()
    if normalized == "RELAXED_TO_MEDIUM":
        normalized = "MEDIUM"
    if normalized not in ALLOWED_CONFIDENCE_REQUIREMENTS:
        raise ValueError("invalid_confidence_requirement")
    return normalized


def _blocker_counts(items: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        for reason in item.get("reasons") or []:
            if str(reason) == "policy_verdict_not_auto_allowed":
                continue
            counts[str(reason)] += 1
    return counts


def _summary_payload(
    items: list[dict[str, Any]],
    *,
    alignment_threshold: int,
    confidence_requirement: str,
    auto_lane_state: str,
    recent_cases: int,
) -> dict[str, Any]:
    readiness = derive_auto_lane_readiness_summary(
        items,
        recent_cases=recent_cases,
        auto_lane_state=auto_lane_state,
    )
    top_blockers = readiness["trend"]["top_blockers"]
    return {
        "alignment_threshold": alignment_threshold,
        "confidence_requirement": confidence_requirement,
        "eligible_count": readiness["counts"]["eligible"],
        "blocked_count": readiness["counts"]["blocked"],
        "eligible_ratio": readiness["trend"]["eligible_ratio"],
        "top_blocker": top_blockers[0]["reason"] if top_blockers else None,
        "readiness_band": readiness["readiness"]["band"],
    }


def _blocker_shift(
    baseline_items: list[dict[str, Any]],
    simulated_items: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    baseline_counts = _blocker_counts(baseline_items)
    simulated_counts = _blocker_counts(simulated_items)
    reasons = sorted(
        set(baseline_counts) | set(simulated_counts),
        key=lambda reason: (
            -abs(simulated_counts.get(reason, 0) - baseline_counts.get(reason, 0)),
            -max(simulated_counts.get(reason, 0), baseline_counts.get(reason, 0)),
            reason,
        ),
    )
    items: list[dict[str, Any]] = []
    for reason in reasons:
        baseline_count = baseline_counts.get(reason, 0)
        simulated_count = simulated_counts.get(reason, 0)
        if baseline_count == simulated_count and baseline_count == 0:
            continue
        items.append(
            {
                "reason": reason,
                "baseline_count": baseline_count,
                "simulated_count": simulated_count,
            }
        )
        if len(items) >= limit:
            break
    return items


def _notes(
    baseline: dict[str, Any],
    simulation: dict[str, Any],
    shifts: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    for shift in shifts:
        if shift["reason"] == "trust_alignment_count_below_threshold" and shift["simulated_count"] < shift["baseline_count"]:
            notes.append("simulation reduced trust-alignment blocking")
            break
    if baseline.get("top_blocker") and baseline.get("top_blocker") == simulation.get("top_blocker"):
        if baseline["top_blocker"] == "confidence_band_not_high":
            notes.append("confidence remains the dominant blocker")
        else:
            notes.append(f"{baseline['top_blocker']} remains the dominant blocker")
    eligible_delta = int(simulation["eligible_count"]) - int(baseline["eligible_count"])
    if eligible_delta > 0:
        notes.append("simulation widened eligibility within the existing lane")
    elif eligible_delta < 0:
        notes.append("simulation narrowed eligibility within the existing lane")
    return notes[:3]


def derive_tuning_preview(
    candidate_contexts: list[dict[str, Any]],
    *,
    alignment_threshold: int = BASELINE_ALIGNMENT_THRESHOLD,
    confidence_requirement: str = BASELINE_CONFIDENCE_REQUIREMENT,
    recent_cases: int = DEFAULT_RECENT_CASES,
    auto_lane_state: str = "AUTO_LANE_FROZEN",
) -> dict[str, Any]:
    normalized_alignment_threshold = _normalize_alignment_threshold(alignment_threshold)
    normalized_confidence_requirement = _normalize_confidence_requirement(confidence_requirement)
    bounded_cases = max(1, min(int(recent_cases), 50))

    if not candidate_contexts:
        return {
            "window": {"recent_cases": bounded_cases, "cases_observed": 0},
            "baseline": {
                "alignment_threshold": BASELINE_ALIGNMENT_THRESHOLD,
                "confidence_requirement": BASELINE_CONFIDENCE_REQUIREMENT,
                "eligible_count": 0,
                "blocked_count": 0,
                "eligible_ratio": 0.0,
                "top_blocker": None,
                "readiness_band": "NOT_READY",
            },
            "simulation": {
                "alignment_threshold": normalized_alignment_threshold,
                "confidence_requirement": normalized_confidence_requirement,
                "eligible_count": 0,
                "blocked_count": 0,
                "eligible_ratio": 0.0,
                "top_blocker": None,
                "readiness_band": "NOT_READY",
            },
            "difference": {
                "eligible_delta": 0,
                "blocked_delta": 0,
                "eligible_ratio_delta": 0.0,
            },
            "blocker_shift": [],
            "notes": ["insufficient evidence for sandbox tuning preview"],
            "stats_available": False,
        }

    baseline_items: list[dict[str, Any]] = []
    simulated_items: list[dict[str, Any]] = []
    for context in candidate_contexts:
        latest_decision = context.get("latest_decision") if isinstance(context.get("latest_decision"), dict) else None
        policy_payload = context.get("policy_payload") if isinstance(context.get("policy_payload"), dict) else None
        base_review = derive_auto_lane_review(
            latest_decision,
            policy_payload,
            alignment_threshold=BASELINE_ALIGNMENT_THRESHOLD,
            confidence_requirement=BASELINE_CONFIDENCE_REQUIREMENT,
            simulate_policy_gate=True,
        )
        sim_review = derive_auto_lane_review(
            latest_decision,
            policy_payload,
            alignment_threshold=normalized_alignment_threshold,
            confidence_requirement=normalized_confidence_requirement,
            simulate_policy_gate=True,
        )
        baseline_items.append(base_review)
        simulated_items.append(sim_review)

    baseline = _summary_payload(
        baseline_items,
        alignment_threshold=BASELINE_ALIGNMENT_THRESHOLD,
        confidence_requirement=BASELINE_CONFIDENCE_REQUIREMENT,
        auto_lane_state=auto_lane_state,
        recent_cases=bounded_cases,
    )
    simulation = _summary_payload(
        simulated_items,
        alignment_threshold=normalized_alignment_threshold,
        confidence_requirement=normalized_confidence_requirement,
        auto_lane_state=auto_lane_state,
        recent_cases=bounded_cases,
    )
    shifts = _blocker_shift(baseline_items, simulated_items)
    return {
        "window": {"recent_cases": bounded_cases, "cases_observed": len(candidate_contexts)},
        "baseline": baseline,
        "simulation": simulation,
        "difference": {
            "eligible_delta": int(simulation["eligible_count"]) - int(baseline["eligible_count"]),
            "blocked_delta": int(simulation["blocked_count"]) - int(baseline["blocked_count"]),
            "eligible_ratio_delta": round(float(simulation["eligible_ratio"]) - float(baseline["eligible_ratio"]), 2),
        },
        "blocker_shift": shifts,
        "notes": _notes(baseline, simulation, shifts),
        "stats_available": True,
    }


def load_policy_tuning_preview(
    *,
    observability_root: Path,
    repo_root: Path,
    alignment_threshold: int | str = BASELINE_ALIGNMENT_THRESHOLD,
    confidence_requirement: str | None = BASELINE_CONFIDENCE_REQUIREMENT,
    recent_cases: int = DEFAULT_RECENT_CASES,
) -> dict[str, Any]:
    contexts = load_auto_lane_candidate_contexts(
        observability_root=observability_root,
        repo_root=repo_root,
        item_limit=max(1, min(int(recent_cases), 50)),
    )
    stats = load_policy_stats(observability_root=observability_root, repo_root=repo_root)
    return derive_tuning_preview(
        contexts,
        alignment_threshold=_normalize_alignment_threshold(alignment_threshold),
        confidence_requirement=_normalize_confidence_requirement(confidence_requirement),
        recent_cases=recent_cases,
        auto_lane_state=str(stats.get("auto_lane_state") or "AUTO_LANE_FROZEN"),
    )
