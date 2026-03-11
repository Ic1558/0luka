from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tools.ops.control_plane_auto_lane_queue import load_auto_lane_candidate_reviews
from tools.ops.control_plane_policy_observability import load_policy_stats


DEFAULT_RECENT_CASES = 20
MIN_READINESS_EVIDENCE = 4
TOP_BLOCKER_LIMIT = 5
READINESS_META_BLOCKERS = {
    "policy_verdict_not_auto_allowed",
}


def _trend_label(previous: int, current: int) -> str:
    if current > previous:
        return "UP"
    if current < previous:
        return "DOWN"
    return "STABLE"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 2)


def _blocker_counts(items: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        for reason in item.get("reasons") or []:
            reason_value = str(reason)
            if reason_value in READINESS_META_BLOCKERS:
                continue
            counts[reason_value] += 1
    return counts


def _top_blockers(
    current_items: list[dict[str, Any]],
    previous_items: list[dict[str, Any]],
    recent_items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    total_counts = _blocker_counts(recent_items)
    current_counts = _blocker_counts(current_items)
    previous_counts = _blocker_counts(previous_items)
    return [
        {
            "reason": reason,
            "count": count,
            "trend": _trend_label(previous_counts.get(reason, 0), current_counts.get(reason, 0)),
        }
        for reason, count in sorted(total_counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _readiness_band(
    *,
    stats: dict[str, Any],
    total_cases: int,
    eligible_ratio: float,
    blocked_count: int,
    top_blockers: list[dict[str, Any]],
    recent_items: list[dict[str, Any]],
) -> dict[str, str]:
    if total_cases < MIN_READINESS_EVIDENCE:
        return {
            "band": "NOT_READY",
            "reason": "insufficient recent evidence for bounded readiness scoring",
        }

    if str(stats.get("auto_lane_state") or "AUTO_LANE_FROZEN") != "AUTO_LANE_ACTIVE":
        return {
            "band": "NOT_READY",
            "reason": "auto lane is currently frozen",
        }

    if any(str(item.get("effective_lane_state") or "") == "AUTO_LANE_FROZEN" for item in recent_items):
        return {
            "band": "NOT_READY",
            "reason": "frozen lane condition appears in the current review window",
        }

    dominant_share = 0.0
    dominant_reason = None
    if blocked_count > 0 and top_blockers:
        dominant_reason = str(top_blockers[0].get("reason") or "")
        dominant_share = float(top_blockers[0].get("count") or 0) / blocked_count

    if eligible_ratio < 0.30:
        return {
            "band": "NOT_READY",
            "reason": "blocked cases still dominate the recent review window",
        }

    if dominant_share > 0.50 and dominant_reason:
        return {
            "band": "NOT_READY",
            "reason": f"{dominant_reason} dominates recent blocked cases",
        }

    if eligible_ratio >= 0.60:
        return {
            "band": "READY",
            "reason": "recent eligibility is strong without a dominant blocking condition",
        }

    return {
        "band": "MARGINAL",
        "reason": "recent eligibility is mixed and blocker pressure remains moderate",
    }


def derive_auto_lane_readiness_summary(
    recent_items: list[dict[str, Any]],
    *,
    recent_cases: int,
    auto_lane_state: str,
) -> dict[str, Any]:
    bounded_cases = max(1, min(int(recent_cases), 50))
    total_cases = len(recent_items)
    eligible_count = sum(1 for item in recent_items if item.get("eligibility_verdict") == "ELIGIBLE")
    blocked_count = sum(1 for item in recent_items if item.get("eligibility_verdict") == "BLOCKED")
    eligible_ratio = _ratio(eligible_count, total_cases)

    split_index = max(1, total_cases // 2) if total_cases else 0
    previous_items = recent_items[split_index:]
    current_items = recent_items[:split_index]
    top_blockers = _top_blockers(current_items, previous_items, recent_items, limit=TOP_BLOCKER_LIMIT)

    readiness = _readiness_band(
        stats={"auto_lane_state": auto_lane_state},
        total_cases=total_cases,
        eligible_ratio=eligible_ratio,
        blocked_count=blocked_count,
        top_blockers=top_blockers,
        recent_items=recent_items,
    )

    return {
        "window": {
            "recent_cases": bounded_cases,
            "cases_observed": total_cases,
            "comparison_slices": {
                "current": len(current_items),
                "previous": len(previous_items),
            },
        },
        "counts": {
            "eligible": eligible_count,
            "blocked": blocked_count,
        },
        "trend": {
            "eligible_ratio": eligible_ratio,
            "top_blockers": top_blockers,
        },
        "readiness": readiness,
    }


def load_auto_lane_readiness(
    *,
    observability_root: Path,
    repo_root: Path,
    recent_cases: int = DEFAULT_RECENT_CASES,
) -> dict[str, Any]:
    bounded_cases = max(1, min(int(recent_cases), 50))
    recent_items = load_auto_lane_candidate_reviews(
        observability_root=observability_root,
        repo_root=repo_root,
        item_limit=bounded_cases,
    )
    stats = load_policy_stats(observability_root=observability_root, repo_root=repo_root)
    return derive_auto_lane_readiness_summary(
        recent_items,
        recent_cases=bounded_cases,
        auto_lane_state=str(stats.get("auto_lane_state") or "AUTO_LANE_FROZEN"),
    )
