from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_tuning_simulator import (
    BASELINE_SUCCESS_THRESHOLD,
    derive_tuning_preview,
)


def test_simulator_returns_deterministic_result(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d1"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d1", "policy_reason": "reason_a"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d2"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d2", "policy_reason": "reason_a"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d3"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d3", "policy_reason": "reason_b"},
        {"event": "EXECUTION_RETRY_REQUESTED", "decision_id": "d4"},
        {"event": "AUTO_RETRY_TRIGGERED", "decision_id": "d4", "policy_reason": "reason_b"},
    ]
    (outbox_dir / "decision_exec_d1_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    (outbox_dir / "decision_exec_d2_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    (audit_dir / "decision_exec_d3_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_d4_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")

    payload = derive_tuning_preview(rows, repo_root=repo_root, simulated_success_threshold=0.80)

    assert payload["baseline_threshold"] == BASELINE_SUCCESS_THRESHOLD
    assert payload["simulated_threshold"] == 0.80
    assert payload["baseline_retry_count"] == 2
    assert payload["simulated_retry_count"] == 2
    assert payload["baseline_success_rate"] == 1.0
    assert payload["simulated_success_rate"] == 1.0
    assert payload["difference"]["retry_reduction"] == 0
    assert payload["stats_available"] is True


def test_simulator_handles_sparse_data_safely(tmp_path) -> None:
    payload = derive_tuning_preview([], repo_root=tmp_path, simulated_success_threshold=0.80)

    assert payload["baseline_threshold"] == BASELINE_SUCCESS_THRESHOLD
    assert payload["simulated_threshold"] == 0.80
    assert payload["baseline_retry_count"] == 0
    assert payload["simulated_retry_count"] == 0
    assert payload["baseline_success_rate"] == 0.0
    assert payload["simulated_success_rate"] == 0.0
    assert payload["difference"]["retry_reduction"] == 0
    assert payload["stats_available"] is False
