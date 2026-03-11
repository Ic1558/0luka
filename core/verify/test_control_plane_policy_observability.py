from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_learning_review import derive_policy_review, load_policy_learning_review
from tools.ops.control_plane_policy_observability import derive_policy_stats, load_policy_stats


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
