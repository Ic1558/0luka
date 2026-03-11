from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_learning_review import derive_policy_review, load_policy_learning_review
from tools.ops.control_plane_auto_lane_queue import load_auto_lane_candidate_queue
from tools.ops.control_plane_auto_lane_trends import load_auto_lane_readiness
from tools.ops.control_plane_policy_observability import derive_policy_stats, load_policy_stats


def _write_auto_lane_window(
    observability_root: Path,
    *,
    total_cases: int,
    eligible_cases: int,
    blocker_reason: str = "trust_alignment_count_below_threshold",
    frozen: bool = False,
    include_sparse_only: bool = False,
) -> None:
    repo_root = observability_root.parent
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for index in range(total_cases):
        decision_id = f"d{index + 1}"
        is_eligible = index < eligible_cases
        blocked_reason = blocker_reason
        should_add_retry_request = True
        if blocker_reason == "mixed" and not is_eligible:
            selector = (index - eligible_cases) % 3
            if selector == 0:
                blocked_reason = "confidence_band_not_high"
            elif selector == 1:
                blocked_reason = "trust_alignment_count_below_threshold"
            else:
                blocked_reason = "execution_outcome_not_failed"
                should_add_retry_request = False
        rows.append(
            {
                "event": "POLICY_EVALUATED",
                "decision_id": decision_id,
                "trace_id": f"t{index + 1}",
                "ts_utc": f"2026-03-11T18:{index:02d}:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": [f"artifact://proof-{index + 1}"],
                "suggestion": "RETRY_RECOMMENDED",
                "confidence_band": "HIGH" if is_eligible or blocked_reason != "confidence_band_not_high" else "LOW",
                "policy_verdict": "AUTO_ALLOWED" if is_eligible or blocked_reason == "execution_outcome_not_failed" else "HUMAN_APPROVAL_REQUIRED",
                "policy_reason": "high_confidence_retry_after_repeated_operator_alignment",
                "alignment_count": 2 if is_eligible or blocked_reason != "trust_alignment_count_below_threshold" else 1,
            }
        )
        if should_add_retry_request and (not include_sparse_only or is_eligible):
            rows.append(
                {
                    "event": "EXECUTION_RETRY_REQUESTED",
                    "decision_id": decision_id,
                    "trace_id": f"t{index + 1}",
                    "ts_utc": f"2026-03-11T18:{index:02d}:10Z",
                    "operator_status": "APPROVED",
                    "proposed_action": "QUARANTINE",
                    "evidence_refs": [f"artifact://proof-{index + 1}"],
                }
            )
            (audit_dir / f"decision_exec_{decision_id}_retry_1.json").write_text(
                json.dumps({"decision": "error"}),
                encoding="utf-8",
            )
    if frozen:
        rows.append(
            {
                "event": "AUTO_RETRY_TRIGGERED",
                "decision_id": "d1",
                "trace_id": "t1",
                "ts_utc": "2026-03-11T19:59:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["artifact://proof-1"],
            }
        )
        rows.append(
            {
                "event": "POLICY_ALIGNMENT_MATCHED",
                "decision_id": "d1",
                "trace_id": "t1",
                "ts_utc": "2026-03-11T19:59:10Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["artifact://proof-1"],
            }
        )
        rows.append(
            {
                "event": "POLICY_ALIGNMENT_MISMATCHED",
                "decision_id": "d2",
                "trace_id": "t2",
                "ts_utc": "2026-03-11T19:59:20Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["artifact://proof-2"],
            }
        )
    log_path = observability_root / "logs" / "decision_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_derive_policy_stats_counts_success_failure_and_alignment(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d1"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d1"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d2"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d2"},
        {"event": "POLICY_ALIGNMENT_MATCHED", "decision_id": "d1"},
        {"event": "POLICY_ALIGNMENT_MATCHED", "decision_id": "d2"},
        {"event": "POLICY_ALIGNMENT_MISMATCHED", "decision_id": "d3"},
    ]

    (outbox_dir / "decision_exec_d1_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    (audit_dir / "decision_exec_d2_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")

    payload = derive_policy_stats(rows, repo_root=repo_root)

    assert payload["auto_retry_triggered"] == 2
    assert payload["auto_retry_success"] == 1
    assert payload["auto_retry_failed"] == 1
    assert payload["alignment_match"] == 2
    assert payload["alignment_mismatch"] == 1
    assert payload["success_rate"] == 0.5
    assert payload["operator_alignment_rate"] == 0.67
    assert payload["policy_state"] == "POLICY_DEGRADED"
    assert payload["auto_lane_state"] == "AUTO_LANE_FROZEN"
    assert payload["auto_lane_reason"] == "policy_degraded"
    assert payload["warning"] == "Policy reliability degraded. Review recommended."


def test_derive_policy_stats_stays_healthy_without_failure_drift(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d1"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d1"},
        {"event": "POLICY_ALIGNMENT_MATCHED", "decision_id": "d1"},
    ]
    (outbox_dir / "decision_exec_d1_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")

    payload = derive_policy_stats(rows, repo_root=repo_root)

    assert payload["auto_retry_triggered"] == 1
    assert payload["auto_retry_success"] == 1
    assert payload["auto_retry_failed"] == 0
    assert payload["policy_state"] == "POLICY_HEALTHY"
    assert payload["auto_lane_state"] == "AUTO_LANE_ACTIVE"
    assert payload["warning"] is None


def test_manual_unfreeze_event_overrides_degraded_auto_lane_state(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    log_path = observability_root / "logs" / "decision_log.jsonl"
    rows = [
        {
            "event": "EXECUTION_RETRY_REQUESTED",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:00:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
        },
        {
            "event": "AUTO_RETRY_TRIGGERED",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:00:01Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
            "confidence_band": "HIGH",
        },
        {
            "event": "POLICY_AUTO_LANE_UNFROZEN",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:10:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
            "operator_note": "manual review completed; re-enable narrow retry lane",
        },
    ]
    log_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    payload = load_policy_stats(observability_root=observability_root, repo_root=repo_root)

    assert payload["auto_lane_state"] == "AUTO_LANE_ACTIVE"
    assert payload["auto_lane_reason"] == "manual_policy_review_completed"
    assert payload["auto_lane_lifecycle_event"] == "POLICY_AUTO_LANE_UNFROZEN"
    assert payload["auto_lane_operator_note"] == "manual review completed; re-enable narrow retry lane"


def test_policy_learning_review_returns_safe_sparse_surface(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"

    payload = load_policy_learning_review(observability_root=observability_root, repo_root=repo_root)

    assert payload["review_flags"] == ["review_insufficient_evidence"]
    assert payload["reason_breakdown"] == []
    assert payload["review_summary"] == "insufficient evidence for strong review conclusions"


def test_policy_learning_review_flags_threshold_alignment_frozen_and_reason_cluster(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"event": "POLICY_EVALUATED", "decision_id": "d1", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "POLICY_EVALUATED", "decision_id": "d2", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "POLICY_EVALUATED", "decision_id": "d3", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "POLICY_EVALUATED", "decision_id": "d4", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d1"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d1", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d2"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d2", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d3"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d3", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d4"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d4", "policy_reason": "high_confidence_retry_after_repeated_operator_alignment"},
        {"event": "POLICY_ALIGNMENT_MATCHED", "decision_id": "d1"},
        {"event": "POLICY_ALIGNMENT_MISMATCHED", "decision_id": "d2"},
        {"event": "POLICY_ALIGNMENT_MISMATCHED", "decision_id": "d3"},
        {"event": "POLICY_ALIGNMENT_MISMATCHED", "decision_id": "d4"},
    ]
    (audit_dir / "decision_exec_d1_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_d2_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_d3_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (outbox_dir / "decision_exec_d4_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")

    stats = derive_policy_stats(rows, repo_root=repo_root)
    payload = derive_policy_review(rows, repo_root=repo_root, stats=stats)

    assert payload["policy_state"] == "POLICY_DEGRADED"
    assert payload["auto_lane_state"] == "AUTO_LANE_FROZEN"
    assert payload["rates"]["auto_retry_success_rate"] == 0.25
    assert payload["rates"]["operator_alignment_rate"] == 0.25
    assert "review_auto_retry_threshold" in payload["review_flags"]
    assert "review_alignment_drift" in payload["review_flags"]
    assert "review_frozen_lane" in payload["review_flags"]
    assert "review_reason_failure_cluster" in payload["review_flags"]
    assert payload["reason_breakdown"][0]["policy_reason"] == "high_confidence_retry_after_repeated_operator_alignment"
    assert payload["reason_breakdown"][0]["failure_count"] == 3


def test_auto_lane_candidate_queue_aggregates_recent_candidates_and_top_blockers(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    runtime_root = tmp_path / "runtime"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:00:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "policy_verdict": "AUTO_ALLOWED",
            "policy_reason": "high_confidence_retry_after_repeated_operator_alignment",
            "alignment_count": 2,
        },
        {
            "event": "EXECUTION_RETRY_REQUESTED",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:00:10Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
        },
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d2",
            "trace_id": "t2",
            "ts_utc": "2026-03-11T18:01:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-2"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "policy_reason": "retry_recommended_but_not_auto_eligible",
            "alignment_count": 1,
        },
        {
            "event": "EXECUTION_RETRY_REQUESTED",
            "decision_id": "d2",
            "trace_id": "t2",
            "ts_utc": "2026-03-11T18:01:10Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-2"],
        },
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d3",
            "trace_id": "t3",
            "ts_utc": "2026-03-11T18:02:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-3"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "LOW",
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "policy_reason": "retry_recommended_but_not_auto_eligible",
            "alignment_count": 1,
        },
    ]
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    (audit_dir / "decision_exec_d1_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_d2_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")

    payload = load_auto_lane_candidate_queue(
        observability_root=observability_root,
        repo_root=repo_root,
        item_limit=10,
    )

    assert payload["summary"]["eligible_count"] == 1
    assert payload["summary"]["blocked_count"] == 2
    assert all(item["candidate_lane"] == "SUPERVISED_RETRY" for item in payload["items"])
    assert any(item["category"] == "ELIGIBLE" for item in payload["items"])


def test_auto_lane_readiness_returns_ready_for_strong_recent_pattern(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    _write_auto_lane_window(observability_root, total_cases=10, eligible_cases=7, blocker_reason="mixed")

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=10,
    )

    assert payload["counts"] == {"eligible": 7, "blocked": 3}
    assert payload["trend"]["eligible_ratio"] == 0.7
    assert payload["readiness"]["band"] == "READY"


def test_auto_lane_readiness_returns_marginal_for_mixed_recent_pattern(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    _write_auto_lane_window(observability_root, total_cases=10, eligible_cases=4, blocker_reason="mixed")

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=10,
    )

    assert payload["counts"] == {"eligible": 4, "blocked": 6}
    assert payload["trend"]["eligible_ratio"] == 0.4
    assert payload["readiness"]["band"] == "MARGINAL"


def test_auto_lane_readiness_returns_not_ready_for_low_eligible_ratio(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    _write_auto_lane_window(observability_root, total_cases=10, eligible_cases=2, blocker_reason="confidence_band_not_high")

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=10,
    )

    assert payload["trend"]["eligible_ratio"] == 0.2
    assert payload["readiness"]["band"] == "NOT_READY"
    assert payload["readiness"]["reason"] == "blocked cases still dominate the recent review window"


def test_auto_lane_readiness_returns_not_ready_when_lane_is_frozen(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "decision_exec_d1_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    _write_auto_lane_window(observability_root, total_cases=10, eligible_cases=7, frozen=True)

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=10,
    )

    assert payload["readiness"]["band"] == "NOT_READY"
    assert payload["readiness"]["reason"] == "auto lane is currently frozen"


def test_auto_lane_readiness_labels_blocker_trends_deterministically(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"
    rows = [
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d1",
            "trace_id": "t1",
            "ts_utc": "2026-03-11T18:00:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-1"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "LOW",
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "alignment_count": 2,
        },
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d2",
            "trace_id": "t2",
            "ts_utc": "2026-03-11T18:01:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-2"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "LOW",
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "alignment_count": 2,
        },
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d3",
            "trace_id": "t3",
            "ts_utc": "2026-03-11T18:02:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-3"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "alignment_count": 1,
        },
        {
            "event": "POLICY_EVALUATED",
            "decision_id": "d4",
            "trace_id": "t4",
            "ts_utc": "2026-03-11T18:03:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-4"],
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "policy_verdict": "AUTO_ALLOWED",
            "alignment_count": 2,
        },
        {
            "event": "EXECUTION_RETRY_REQUESTED",
            "decision_id": "d4",
            "trace_id": "t4",
            "ts_utc": "2026-03-11T18:03:10Z",
            "operator_status": "APPROVED",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["artifact://proof-4"],
        },
    ]
    log_path = observability_root / "logs" / "decision_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=4,
    )

    top_blockers = {item["reason"]: item["trend"] for item in payload["trend"]["top_blockers"]}
    assert top_blockers["confidence_band_not_high"] == "DOWN"
    assert top_blockers["trust_alignment_count_below_threshold"] == "UP"


def test_auto_lane_readiness_returns_safe_sparse_surface_without_recent_cases(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    observability_root = repo_root / "observability"

    payload = load_auto_lane_readiness(
        observability_root=observability_root,
        repo_root=repo_root,
        recent_cases=20,
    )

    assert payload["counts"] == {"eligible": 0, "blocked": 0}
    assert payload["trend"]["eligible_ratio"] == 0.0
    assert payload["trend"]["top_blockers"] == []
    assert payload["readiness"]["band"] == "NOT_READY"
