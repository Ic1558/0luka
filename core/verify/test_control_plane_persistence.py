from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.control_plane_persistence import (  # noqa: E402
    DecisionPersistenceError,
    make_decision_id,
    read_latest_decision,
    record_operator_decision,
    write_pending_decision,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "runtime", tmp_path / "observability"


def _proposal(*, trace_id: str = "trace-001", ts_utc: str = "2026-03-11T12:00:00Z") -> dict:
    base = {
        "trace_id": trace_id,
        "ts_utc": ts_utc,
        "signal_received": "policy_drift_detected",
        "proposed_action": "ESCALATE",
        "evidence_refs": ["proof_pack:run_001"],
        "operator_status": "PENDING",
        "operator_note": None,
    }
    base["decision_id"] = make_decision_id(
        trace_id=base["trace_id"],
        ts_utc=base["ts_utc"],
        signal_received=base["signal_received"],
        proposed_action=base["proposed_action"],
    )
    return base


def test_valid_pending_proposal_writes_latest_and_appends_ledger(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = _proposal()

    payload = write_pending_decision(proposal, runtime_root, observability_root)

    assert payload == proposal
    assert _read_json(runtime_root / "state" / "decision_latest.json") == proposal
    assert _read_jsonl(observability_root / "logs" / "decision_log.jsonl") == [
        {
            "event": "PROPOSAL_CREATED",
            "decision_id": proposal["decision_id"],
            "trace_id": proposal["trace_id"],
            "ts_utc": proposal["ts_utc"],
            "operator_status": "PENDING",
            "proposed_action": "ESCALATE",
            "evidence_refs": ["proof_pack:run_001"],
        }
    ]


def test_invalid_proposal_is_rejected_fail_closed(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = _proposal()
    proposal["trace_id"] = ""

    try:
        write_pending_decision(proposal, runtime_root, observability_root)
    except DecisionPersistenceError as exc:
        assert str(exc) == "invalid_trace_id"
    else:
        raise AssertionError("expected DecisionPersistenceError")

    assert not (runtime_root / "state" / "decision_latest.json").exists()
    assert not (observability_root / "logs" / "decision_log.jsonl").exists()


def test_overwrite_of_existing_pending_proposal_is_rejected(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    write_pending_decision(_proposal(), runtime_root, observability_root)
    new_proposal = _proposal(trace_id="trace-002", ts_utc="2026-03-11T12:05:00Z")

    try:
        write_pending_decision(new_proposal, runtime_root, observability_root)
    except DecisionPersistenceError as exc:
        assert str(exc) == "pending_decision_exists"
    else:
        raise AssertionError("expected DecisionPersistenceError")

    assert read_latest_decision(runtime_root)["decision_id"] != new_proposal["decision_id"]


def test_operator_approve_appends_ledger_and_updates_latest_state(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = write_pending_decision(_proposal(), runtime_root, observability_root)

    updated = record_operator_decision(
        proposal["decision_id"],
        "APPROVED",
        runtime_root,
        observability_root,
        operator_note="approved by operator",
    )

    assert updated["operator_status"] == "APPROVED"
    assert updated["operator_note"] == "approved by operator"
    assert _read_json(runtime_root / "state" / "decision_latest.json")["operator_status"] == "APPROVED"
    assert _read_jsonl(observability_root / "logs" / "decision_log.jsonl")[-1]["event"] == "OPERATOR_APPROVED"


def test_operator_reject_appends_ledger_and_updates_latest_state(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = write_pending_decision(_proposal(), runtime_root, observability_root)

    updated = record_operator_decision(
        proposal["decision_id"],
        "REJECTED",
        runtime_root,
        observability_root,
        operator_note="not justified",
    )

    assert updated["operator_status"] == "REJECTED"
    assert updated["operator_note"] == "not justified"
    assert _read_jsonl(observability_root / "logs" / "decision_log.jsonl")[-1]["event"] == "OPERATOR_REJECTED"


def test_ledger_remains_append_only(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = write_pending_decision(_proposal(), runtime_root, observability_root)
    initial_log = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8")

    record_operator_decision(proposal["decision_id"], "APPROVED", runtime_root, observability_root)

    final_log = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8")
    assert final_log.startswith(initial_log)
    assert len(_read_jsonl(observability_root / "logs" / "decision_log.jsonl")) == 2


def test_malformed_existing_latest_state_fails_closed(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    latest_path = runtime_root / "state" / "decision_latest.json"
    latest_path.parent.mkdir(parents=True)
    latest_path.write_text("{bad-json", encoding="utf-8")

    try:
        write_pending_decision(_proposal(), runtime_root, observability_root)
    except DecisionPersistenceError as exc:
        assert str(exc) == "unreadable_decision_latest.json"
    else:
        raise AssertionError("expected DecisionPersistenceError")

    assert not (observability_root / "logs" / "decision_log.jsonl").exists()


def test_enums_are_strictly_enforced(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = _proposal()
    proposal["proposed_action"] = "RETRY_TASK"
    proposal["decision_id"] = make_decision_id(
        trace_id=proposal["trace_id"],
        ts_utc=proposal["ts_utc"],
        signal_received=proposal["signal_received"],
        proposed_action="ESCALATE",
    )

    try:
        write_pending_decision(proposal, runtime_root, observability_root)
    except DecisionPersistenceError as exc:
        assert str(exc) == "invalid_proposed_action"
    else:
        raise AssertionError("expected DecisionPersistenceError")


def test_evidence_refs_must_be_non_empty(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    proposal = _proposal()
    proposal["evidence_refs"] = []

    try:
        write_pending_decision(proposal, runtime_root, observability_root)
    except DecisionPersistenceError as exc:
        assert str(exc) == "invalid_evidence_refs"
    else:
        raise AssertionError("expected DecisionPersistenceError")


def test_no_execution_runtime_side_effects_occur(tmp_path: Path) -> None:
    runtime_root, observability_root = _paths(tmp_path)
    write_pending_decision(_proposal(), runtime_root, observability_root)

    runtime_files = sorted(path.relative_to(tmp_path).as_posix() for path in runtime_root.rglob("*") if path.is_file())
    observability_files = sorted(
        path.relative_to(tmp_path).as_posix() for path in observability_root.rglob("*") if path.is_file()
    )

    assert runtime_files == ["runtime/state/decision_latest.json"]
    assert observability_files == ["observability/logs/decision_log.jsonl"]
