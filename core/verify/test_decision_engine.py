from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.control_plane_persistence import read_latest_decision
from tools.ops.decision_engine import classify_once, generate_proposal_once, map_signal_to_action


def test_nominal_classification() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision == "nominal"


def test_operator_failure() -> None:
    decision = classify_once(
        {"ok": False},
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision == "drift_detected"


def test_runtime_failure() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": False},
        {"drift_count": 0},
    )

    assert decision == "drift_detected"


def test_policy_drift() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {"drift_count": 1},
    )

    assert decision == "drift_detected"


def test_missing_fields_returns_none() -> None:
    decision = classify_once(
        {"ok": True},
        {"ok": True},
        {},
    )

    assert decision is None


def test_malformed_input_returns_none() -> None:
    decision = classify_once(
        [],
        {"ok": True},
        {"drift_count": 0},
    )

    assert decision is None


def test_signal_mapping_missing_proof_to_review_proof() -> None:
    assert map_signal_to_action("MISSING_PROOF") == "REVIEW_PROOF"


def test_signal_mapping_inconsistent_to_quarantine() -> None:
    assert map_signal_to_action("INCONSISTENT") == "QUARANTINE"


def test_signal_mapping_unknown_to_escalate() -> None:
    assert map_signal_to_action("SOMETHING_NEW") == "ESCALATE"


def test_evidence_refs_are_propagated_into_persisted_proposal(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"

    proposal = generate_proposal_once(
        trace_id="trace-100",
        signal_received="MISSING_PROOF",
        evidence_refs=["proof_pack:run_100"],
        ts_utc="2026-03-11T12:10:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )

    assert proposal is not None
    assert proposal["evidence_refs"] == ["proof_pack:run_100"]
    latest = read_latest_decision(runtime_root)
    assert latest is not None
    assert latest["evidence_refs"] == ["proof_pack:run_100"]
    ledger_rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert ledger_rows[-1]["evidence_refs"] == ["proof_pack:run_100"]


def test_single_pending_rule_skips_writing_new_proposal(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    initial = generate_proposal_once(
        trace_id="trace-101",
        signal_received="INCONSISTENT",
        evidence_refs=["proof_pack:run_101"],
        ts_utc="2026-03-11T12:11:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )

    latest_before = (runtime_root / "state" / "decision_latest.json").read_text(encoding="utf-8")
    log_before = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8")
    result = generate_proposal_once(
        trace_id="trace-102",
        signal_received="UNKNOWN",
        evidence_refs=["proof_pack:run_102"],
        ts_utc="2026-03-11T12:12:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )

    assert initial is not None
    assert result is None
    assert (runtime_root / "state" / "decision_latest.json").read_text(encoding="utf-8") == latest_before
    assert (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8") == log_before


def test_no_action_signals_skip_persistence(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"

    result_complete = generate_proposal_once(
        trace_id="trace-103",
        signal_received="COMPLETE",
        evidence_refs=["proof_pack:run_103"],
        ts_utc="2026-03-11T12:13:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )
    result_nominal = generate_proposal_once(
        trace_id="trace-104",
        signal_received="NOMINAL",
        evidence_refs=["proof_pack:run_104"],
        ts_utc="2026-03-11T12:14:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )

    assert result_complete is None
    assert result_nominal is None
    assert not (runtime_root / "state" / "decision_latest.json").exists()
    assert not (observability_root / "logs" / "decision_log.jsonl").exists()


def test_missing_evidence_refs_fails_closed(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"

    try:
        generate_proposal_once(
            trace_id="trace-105",
            signal_received="MISSING_PROOF",
            evidence_refs=[],
            ts_utc="2026-03-11T12:15:00Z",
            runtime_root=runtime_root,
            observability_root=observability_root,
        )
    except Exception as exc:
        assert str(exc) == "invalid_evidence_refs"
    else:
        raise AssertionError("expected invalid_evidence_refs")


def test_no_execution_calls_are_introduced(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"

    monkeypatch.setattr(
        "tools.ops.decision_engine.task_dispatcher",
        object(),
        raising=False,
    )
    monkeypatch.setattr(
        "tools.ops.decision_engine.remediation_engine",
        object(),
        raising=False,
    )
    monkeypatch.setattr(
        "tools.ops.decision_engine.bridge_workers",
        object(),
        raising=False,
    )

    proposal = generate_proposal_once(
        trace_id="trace-106",
        signal_received="UNKNOWN",
        evidence_refs=["proof_pack:run_106"],
        ts_utc="2026-03-11T12:16:00Z",
        runtime_root=runtime_root,
        observability_root=observability_root,
    )

    assert proposal is not None
    assert proposal["proposed_action"] == "ESCALATE"
