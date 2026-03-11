from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_suggestions import (
    SUGGESTION_ESCALATE,
    SUGGESTION_NO_ACTION,
    SUGGESTION_RETRY,
    derive_suggestion,
    load_latest_suggestion,
)
from tools.ops.control_plane_persistence import make_decision_id


def test_approved_failed_returns_retry_suggestion() -> None:
    payload = derive_suggestion(
        {
            "decision_id": "decision_1",
            "trace_id": "trace_1",
            "operator_status": "APPROVED",
        },
        {"outcome_status": "EXECUTION_FAILED"},
    )

    assert payload["suggestion"] == SUGGESTION_RETRY
    assert payload["reason"] == "execution_failed_after_approved_decision"


def test_approved_unknown_returns_escalate_suggestion() -> None:
    payload = derive_suggestion(
        {
            "decision_id": "decision_2",
            "trace_id": "trace_2",
            "operator_status": "APPROVED",
        },
        {"outcome_status": "EXECUTION_UNKNOWN"},
    )

    assert payload["suggestion"] == SUGGESTION_ESCALATE
    assert payload["reason"] == "execution_outcome_unknown_after_approved_decision"


def test_approved_succeeded_returns_no_action_suggestion() -> None:
    payload = derive_suggestion(
        {
            "decision_id": "decision_3",
            "trace_id": "trace_3",
            "operator_status": "APPROVED",
        },
        {"outcome_status": "EXECUTION_SUCCEEDED"},
    )

    assert payload["suggestion"] == SUGGESTION_NO_ACTION
    assert payload["reason"] == "execution_succeeded"


def test_missing_decision_returns_no_action_suggestion() -> None:
    payload = derive_suggestion(None, None)

    assert payload["suggestion"] == SUGGESTION_NO_ACTION
    assert payload["reason"] == "no_latest_decision"


def test_load_latest_suggestion_is_deterministic_for_failed_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    decision_id = make_decision_id(
        trace_id="trace_det",
        ts_utc="2026-03-11T16:00:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_det",
                "signal_received": "INCONSISTENT",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:trace_det"],
                "ts_utc": "2026-03-11T16:00:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        json.dumps(
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision_id,
                "trace_id": "trace_det",
                "ts_utc": "2026-03-11T16:00:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:trace_det"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")

    first = load_latest_suggestion(
        runtime_root=runtime_root,
        observability_root=observability_root,
        repo_root=repo_root,
    )
    second = load_latest_suggestion(
        runtime_root=runtime_root,
        observability_root=observability_root,
        repo_root=repo_root,
    )

    assert first == second
    assert first["suggestion"] == SUGGESTION_RETRY
