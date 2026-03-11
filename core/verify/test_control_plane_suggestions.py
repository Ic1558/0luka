from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_suggestions import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
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
    assert payload["confidence_score"] == 0.9
    assert payload["confidence_band"] == CONFIDENCE_HIGH
    assert payload["reason"] == "execution_failed_after_approved_decision"
    assert payload["root_cause_hint"] == "deterministic execution failure observed after approved handoff"


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
    assert payload["confidence_score"] == 0.65
    assert payload["confidence_band"] == CONFIDENCE_MEDIUM
    assert payload["reason"] == "execution_outcome_unknown_after_approved_decision"
    assert payload["root_cause_hint"] == "downstream result not safely reconcilable from current execution surfaces"


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
    assert payload["confidence_score"] == 0.95
    assert payload["confidence_band"] == CONFIDENCE_HIGH
    assert payload["reason"] == "execution_succeeded"
    assert payload["root_cause_hint"] == "execution completed successfully; no further action suggested"


def test_missing_decision_returns_no_action_suggestion() -> None:
    payload = derive_suggestion(None, None)

    assert payload["suggestion"] == SUGGESTION_NO_ACTION
    assert payload["confidence_score"] == 0.2
    assert payload["confidence_band"] == CONFIDENCE_LOW
    assert payload["reason"] == "no_latest_decision"
    assert payload["root_cause_hint"] == "no latest decision available for suggestion analysis"


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
    assert first["confidence_band"] == CONFIDENCE_HIGH


def test_handoff_only_returns_low_confidence_no_action_hint() -> None:
    payload = derive_suggestion(
        {
            "decision_id": "decision_4",
            "trace_id": "trace_4",
            "operator_status": "APPROVED",
        },
        {"outcome_status": "HANDOFF_ONLY"},
    )

    assert payload["suggestion"] == SUGGESTION_NO_ACTION
    assert payload["confidence_score"] == 0.45
    assert payload["confidence_band"] == CONFIDENCE_LOW
    assert payload["reason"] == "waiting_for_confirmed_execution_outcome"
    assert payload["root_cause_hint"] == "execution was handed off but no confirmed downstream outcome is available"
