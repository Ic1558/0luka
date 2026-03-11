from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_observability import derive_policy_stats


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
    assert payload["warning"] is None
