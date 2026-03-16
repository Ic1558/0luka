"""AG-45: Operator Decision Session Memory — test suite.

Tests:
  A. Decision Memory Policy Unit Tests
  B. Operator Decision Memory Unit Tests
  C. Integration Tests
  D. Safety Invariants
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmpdir() -> str:
    td = tempfile.mkdtemp()
    os.environ["LUKA_RUNTIME_ROOT"] = td
    (Path(td) / "state").mkdir(parents=True, exist_ok=True)
    return td


def _make_pkg(did: str, dtype: str = "APPROVE_REPAIR_WAVE", target: str = "wave-001",
              priority: str = "HIGH", status: str = "PROPOSED") -> dict:
    return {
        "decision_id": did,
        "decision_type": dtype,
        "target_ref": target,
        "priority": priority,
        "status": status,
        "ts": "2026-03-16T00:00:00Z",
        "operator_action_required": True,
        "summary": "test",
        "rationale": "",
        "risks": [],
        "alternatives": [],
        "evidence_refs": ["test"],
    }


def _write_packages_log(td: str, packages: list) -> None:
    path = Path(td) / "state" / "operator_decision_packages.jsonl"
    with path.open("w") as f:
        for pkg in packages:
            f.write(json.dumps(pkg) + "\n")


def _write_queue(td: str, packages: list) -> None:
    path = Path(td) / "state" / "operator_decision_queue.json"
    path.write_text(json.dumps({"packages": packages, "pending": len(packages)}))


def _write_queue_log(td: str, rows: list) -> None:
    path = Path(td) / "state" / "decision_queue_log.jsonl"
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_queue_state(td: str, entries: dict) -> None:
    path = Path(td) / "state" / "decision_queue_state.json"
    path.write_text(json.dumps({"entries": entries}))


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Decision Memory Policy Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionMemoryPolicy:

    def test_all_pattern_classes_defined(self):
        from core.audit.decision_memory_policy import MEMORY_PATTERNS
        required = {
            "repeated_deferral_pattern",
            "repeated_supersede_pattern",
            "recurring_high_risk_component_decision",
            "recurring_governance_review_requirement",
            "stale_decision_reopen_pattern",
            "repeated_pause_campaign_recommendation",
        }
        assert required.issubset(set(MEMORY_PATTERNS.keys()))

    def test_valid_memory_pattern_known(self):
        from core.audit.decision_memory_policy import valid_memory_pattern
        assert valid_memory_pattern("repeated_deferral_pattern") is True

    def test_valid_memory_pattern_unknown(self):
        from core.audit.decision_memory_policy import valid_memory_pattern
        assert valid_memory_pattern("NOT_A_PATTERN") is False

    def test_recurrence_threshold_for_known(self):
        from core.audit.decision_memory_policy import recurrence_threshold_for
        threshold = recurrence_threshold_for("repeated_deferral_pattern")
        assert isinstance(threshold, int) and threshold >= 1

    def test_should_attach_memory_context_same_type(self):
        from core.audit.decision_memory_policy import should_attach_memory_context
        decision = {"decision_type": "APPROVE_REPAIR_WAVE", "target_ref": "wave-001"}
        memory   = {"decision_type": "APPROVE_REPAIR_WAVE", "target_ref": "wave-001"}
        assert should_attach_memory_context(decision, memory) is True

    def test_should_attach_memory_context_same_target(self):
        from core.audit.decision_memory_policy import should_attach_memory_context
        decision = {"decision_type": "APPROVE_REPAIR_WAVE",  "target_ref": "wave-001"}
        memory   = {"decision_type": "DEFER_REPAIR_WAVE",    "target_ref": "wave-001"}
        assert should_attach_memory_context(decision, memory) is True

    def test_should_not_attach_memory_context_unrelated(self):
        from core.audit.decision_memory_policy import should_attach_memory_context
        decision = {"decision_type": "APPROVE_REPAIR_WAVE",  "target_ref": "wave-001"}
        memory   = {"decision_type": "PAUSE_NEW_CAMPAIGNS",  "target_ref": "campaign-system"}
        assert should_attach_memory_context(decision, memory) is False


# ---------------------------------------------------------------------------
# Suite B: Operator Decision Memory Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionMemoryUnit:

    def test_detect_decision_recurrence_flags_repeated_deferrals(self):
        td = _make_tmpdir()
        # Two packages with same type/target, both deferred
        pkgs = [
            _make_pkg("d-001", "APPROVE_REPAIR_WAVE", "wave-001", status="DEFERRED"),
            _make_pkg("d-002", "APPROVE_REPAIR_WAVE", "wave-001", status="DEFERRED"),
        ]
        _write_packages_log(td, pkgs)

        from core.audit.operator_decision_memory import detect_decision_recurrence
        recurrences = detect_decision_recurrence(pkgs, {}, [])
        patterns = [r["pattern"] for r in recurrences]
        assert "repeated_deferral_pattern" in patterns

    def test_detect_decision_recurrence_flags_repeated_supersedes(self):
        td = _make_tmpdir()
        pkgs = [
            _make_pkg("d-001", "APPROVE_REPAIR_WAVE", "wave-001", status="SUPERSEDED"),
            _make_pkg("d-002", "APPROVE_REPAIR_WAVE", "wave-001", status="SUPERSEDED"),
        ]
        from core.audit.operator_decision_memory import detect_decision_recurrence
        recurrences = detect_decision_recurrence(pkgs, {}, [])
        patterns = [r["pattern"] for r in recurrences]
        assert "repeated_supersede_pattern" in patterns

    def test_detect_decision_recurrence_high_risk_recurring(self):
        td = _make_tmpdir()
        pkgs = [
            _make_pkg("d-001", "ESCALATE_HIGH_RISK_COMPONENT", "comp-A"),
            _make_pkg("d-002", "ESCALATE_HIGH_RISK_COMPONENT", "comp-A"),
        ]
        from core.audit.operator_decision_memory import detect_decision_recurrence
        recurrences = detect_decision_recurrence(pkgs, {}, [])
        patterns = [r["pattern"] for r in recurrences]
        assert "recurring_high_risk_component_decision" in patterns

    def test_build_decision_session_memory_contains_required_fields(self):
        td = _make_tmpdir()
        recurrences = [{
            "pattern": "repeated_deferral_pattern",
            "decision_type": "APPROVE_REPAIR_WAVE",
            "target_ref": "wave-001",
            "count": 3,
            "decision_ids": ["d-001", "d-002", "d-003"],
        }]
        from core.audit.operator_decision_memory import build_decision_session_memory
        memories = build_decision_session_memory(recurrences, {})
        assert len(memories) == 1
        m = memories[0]
        required = {"memory_id", "decision_type", "target_ref", "recurrence_class",
                    "prior_occurrences", "last_outcome", "related_decision_ids",
                    "summary", "evidence_refs"}
        assert required.issubset(set(m.keys()))

    def test_attach_memory_context_does_not_mutate_decision_state(self):
        td = _make_tmpdir()
        pkg = _make_pkg("d-001", "APPROVE_REPAIR_WAVE", "wave-001")
        original_status = pkg["status"]
        memory = {
            "memory_id": "mem-abc",
            "decision_type": "APPROVE_REPAIR_WAVE",
            "target_ref": "wave-001",
            "recurrence_class": "repeated_deferral_pattern",
            "prior_occurrences": 2,
            "last_outcome": "DEFERRED",
            "related_decision_ids": ["d-000"],
            "summary": "Deferred twice before.",
            "evidence_refs": [],
        }
        from core.audit.operator_decision_memory import attach_memory_context_to_open_decisions
        enriched = attach_memory_context_to_open_decisions([pkg], [memory])
        # Original not mutated
        assert pkg.get("memory_context") is None
        # Enriched copy has context
        assert "memory_context" in enriched[0]
        # Decision state unchanged
        assert enriched[0]["status"] == original_status
        assert enriched[0]["priority"] == pkg["priority"]

    def test_store_decision_memory_writes_outputs(self):
        td = _make_tmpdir()
        report = {
            "ts": "2026-03-16T00:00:00Z",
            "run_id": "run-001",
            "memory_entries": 0,
            "memories": [],
            "enriched_packages": [],
            "pattern_counts": {},
            "top_pattern": None,
            "repeated_deferrals": 0,
            "repeated_supersedes": 0,
            "total_history_records": 0,
            "operator_action_required": True,
        }
        from core.audit.operator_decision_memory import store_decision_memory
        store_decision_memory(report, td)
        state = Path(td) / "state"
        assert (state / "operator_decision_memory_log.jsonl").exists()
        assert (state / "operator_decision_memory_latest.json").exists()
        assert (state / "operator_decision_memory_index.json").exists()


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_operator_decision_memory_generates_outputs(self):
        td = _make_tmpdir()
        from core.audit.operator_decision_memory import run_operator_decision_memory
        result = run_operator_decision_memory(td)
        assert result["ok"] is True

    def test_run_generates_three_output_files(self):
        td = _make_tmpdir()
        from core.audit.operator_decision_memory import run_operator_decision_memory
        run_operator_decision_memory(td)
        state = Path(td) / "state"
        assert (state / "operator_decision_memory_log.jsonl").exists()
        assert (state / "operator_decision_memory_latest.json").exists()
        assert (state / "operator_decision_memory_index.json").exists()

    def test_run_with_deferred_packages_detects_recurrence(self):
        td = _make_tmpdir()
        pkgs = [
            _make_pkg("d-001", "APPROVE_REPAIR_WAVE", "wave-001", status="DEFERRED"),
            _make_pkg("d-002", "APPROVE_REPAIR_WAVE", "wave-001", status="DEFERRED"),
        ]
        _write_packages_log(td, pkgs)
        _write_queue(td, pkgs)
        from core.audit.operator_decision_memory import run_operator_decision_memory
        result = run_operator_decision_memory(td)
        assert result["ok"] is True
        assert result["memory_entries"] >= 1

    def test_run_empty_state_defaults_gracefully(self):
        td = _make_tmpdir()
        from core.audit.operator_decision_memory import run_operator_decision_memory
        result = run_operator_decision_memory(td)
        assert result["ok"] is True
        assert result["memory_entries"] == 0

    def test_api_decision_memory_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_memory import decision_memory_latest
        result = asyncio.run(decision_memory_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_decision_memory_index_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_memory import decision_memory_index
        result = asyncio.run(decision_memory_index())
        assert result["ok"] is True
        assert "index" in result

    def test_api_decision_memory_context_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_memory import decision_memory_context
        result = asyncio.run(decision_memory_context())
        assert result["ok"] is True
        assert "enriched_packages" in result

    def test_api_decision_memory_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_memory import decision_memory_run
        req = _mock_request({})
        resp = asyncio.run(decision_memory_run(req))
        assert resp.status_code == 403

    def test_api_decision_memory_run_generates_outputs(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_memory import decision_memory_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(decision_memory_run(req))
        import json as _json
        data = _json.loads(resp.body)
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_operator_decision_memory_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        gov_path.write_text(json.dumps({"f-001": {"status": "ESCALATED"}}))
        mtime_before = gov_path.stat().st_mtime
        from core.audit.operator_decision_memory import run_operator_decision_memory
        run_operator_decision_memory(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_operator_decision_memory_does_not_mutate_queue_state(self):
        td = _make_tmpdir()
        pkgs = [_make_pkg("d-001")]
        _write_queue(td, pkgs)
        q_path = Path(td) / "state" / "operator_decision_queue.json"
        mtime_before = q_path.stat().st_mtime
        from core.audit.operator_decision_memory import run_operator_decision_memory
        run_operator_decision_memory(td)
        assert q_path.stat().st_mtime == mtime_before

    def test_operator_decision_memory_does_not_execute_repairs(self):
        td = _make_tmpdir()
        from core.audit.operator_decision_memory import run_operator_decision_memory
        run_operator_decision_memory(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_operator_decision_memory_is_context_only(self):
        td = _make_tmpdir()
        pkgs = [_make_pkg("d-001")]
        _write_queue(td, pkgs)
        _write_packages_log(td, pkgs)
        from core.audit.operator_decision_memory import run_operator_decision_memory
        run_operator_decision_memory(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "audit_baseline.py",
            "repair_campaign_log.jsonl",
            "decision_queue_state.json",      # AG-44 state — not ours to write
            "decision_queue_log.jsonl",       # AG-44 audit log — not ours to write
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_attach_context_does_not_change_priority(self):
        td = _make_tmpdir()
        pkg = _make_pkg("d-001", priority="HIGH")
        memory = {
            "memory_id": "mem-001",
            "decision_type": "APPROVE_REPAIR_WAVE",
            "target_ref": "wave-001",
            "recurrence_class": "repeated_deferral_pattern",
            "prior_occurrences": 2,
            "last_outcome": "DEFERRED",
            "related_decision_ids": [],
            "summary": "test",
            "evidence_refs": [],
        }
        from core.audit.operator_decision_memory import attach_memory_context_to_open_decisions
        enriched = attach_memory_context_to_open_decisions([pkg], [memory])
        assert enriched[0]["priority"] == "HIGH"
