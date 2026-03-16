"""AG-32: Drift Governance & Review Control Plane — test suite.

Suites:
  1. StatusTransitions     — valid/invalid lifecycle state changes
  2. OperatorActions       — accept / dismiss / escalate / resolve / promote_to_baseline
  3. PromoteToBaseline     — proposal artifact created, audit_baseline.py NOT modified
  4. GovStore              — append-only log, atomic status, read helpers
  5. APIGate               — all write endpoints reject missing operator_id (403)
  6. APIRead               — GET endpoints return correct structure
  7. SafetyInvariants      — no mutation of AG-31 outputs, no baseline file mutation
  8. SmokeGovernance       — full lifecycle: OPEN → accept → promote → resolve
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TempRuntime:
    def __enter__(self) -> "Path":
        self._td = tempfile.mkdtemp()
        os.environ["LUKA_RUNTIME_ROOT"] = self._td
        (Path(self._td) / "state").mkdir(parents=True, exist_ok=True)
        return Path(self._td)

    def __exit__(self, *_: object) -> None:
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self._td, ignore_errors=True)


def _sentinel_file(rt: Path, name: str, content: str = '{"sentinel":"unchanged"}\n') -> Path:
    p = rt / "state" / name
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Suite 1 — StatusTransitions
# ---------------------------------------------------------------------------

class TestStatusTransitions(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.drift_governance import (
            VALID_STATES, ALLOWED_TRANSITIONS, _validate_transition
        )
        self.valid_states = VALID_STATES
        self.transitions = ALLOWED_TRANSITIONS
        self.validate = _validate_transition

    def test_all_required_states_defined(self) -> None:
        required = {"OPEN", "ACCEPTED", "DISMISSED", "ESCALATED", "RESOLVED"}
        self.assertEqual(required, self.valid_states & required)

    def test_open_to_accepted_allowed(self) -> None:
        with _TempRuntime():
            self.validate("finding-new", "ACCEPTED")  # no-op, OPEN is default

    def test_open_to_dismissed_allowed(self) -> None:
        with _TempRuntime():
            self.validate("finding-new", "DISMISSED")

    def test_open_to_escalated_allowed(self) -> None:
        with _TempRuntime():
            self.validate("finding-new", "ESCALATED")

    def test_open_to_resolved_not_directly_allowed(self) -> None:
        with _TempRuntime():
            with self.assertRaises(ValueError):
                self.validate("finding-new", "RESOLVED")

    def test_resolved_to_open_allowed_re_emerge(self) -> None:
        """RESOLVED findings can be re-opened if drift re-emerges."""
        self.assertIn("OPEN", self.transitions["RESOLVED"])

    def test_accepted_to_escalated_allowed(self) -> None:
        self.assertIn("ESCALATED", self.transitions["ACCEPTED"])

    def test_dismissed_to_escalated_allowed(self) -> None:
        self.assertIn("ESCALATED", self.transitions["DISMISSED"])


# ---------------------------------------------------------------------------
# Suite 2 — OperatorActions
# ---------------------------------------------------------------------------

class TestOperatorActions(unittest.TestCase):

    def test_accept_finding_sets_status_accepted(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding
            from core.audit.drift_governance_store import get_finding_status
            accept_finding("f-001", operator_id="boss", note="known naming drift")
            rec = get_finding_status("f-001")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["status"], "ACCEPTED")
            self.assertEqual(rec["operator_id"], "boss")

    def test_dismiss_finding_sets_status_dismissed(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import dismiss_finding
            from core.audit.drift_governance_store import get_finding_status
            dismiss_finding("f-002", operator_id="boss")
            rec = get_finding_status("f-002")
            self.assertEqual(rec["status"], "DISMISSED")

    def test_escalate_finding_sets_status_escalated(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import escalate_finding
            from core.audit.drift_governance_store import get_finding_status
            escalate_finding("f-003", operator_id="boss", note="needs patch")
            rec = get_finding_status("f-003")
            self.assertEqual(rec["status"], "ESCALATED")

    def test_resolve_finding_sets_status_resolved(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding, resolve_finding
            from core.audit.drift_governance_store import get_finding_status
            accept_finding("f-004", operator_id="boss")
            resolve_finding("f-004", operator_id="boss", note="fixed in PR #999")
            rec = get_finding_status("f-004")
            self.assertEqual(rec["status"], "RESOLVED")

    def test_accept_requires_operator_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding
            with self.assertRaises(ValueError):
                accept_finding("f-005", operator_id="")

    def test_dismiss_requires_operator_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import dismiss_finding
            with self.assertRaises(ValueError):
                dismiss_finding("f-006", operator_id="   ")

    def test_escalate_requires_operator_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import escalate_finding
            with self.assertRaises(ValueError):
                escalate_finding("f-007", operator_id="")

    def test_resolve_requires_operator_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding, resolve_finding
            accept_finding("f-008", operator_id="boss")
            with self.assertRaises(ValueError):
                resolve_finding("f-008", operator_id="")

    def test_invalid_transition_raises_value_error(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import resolve_finding
            with self.assertRaises(ValueError):
                resolve_finding("f-new", operator_id="boss")  # OPEN→RESOLVED not allowed

    def test_actions_append_to_governance_log(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance import accept_finding, escalate_finding
            accept_finding("f-010", operator_id="boss")
            escalate_finding("f-010", operator_id="boss")
            log_path = rt / "state" / "drift_governance_log.jsonl"
            self.assertTrue(log_path.exists())
            lines = log_path.read_text().strip().splitlines()
            self.assertGreaterEqual(len(lines), 2)

    def test_operator_id_stored_in_status_record(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding
            from core.audit.drift_governance_store import get_finding_status
            accept_finding("f-011", operator_id="alice")
            rec = get_finding_status("f-011")
            self.assertEqual(rec["operator_id"], "alice")

    def test_note_stored_in_status_record(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding
            from core.audit.drift_governance_store import get_finding_status
            accept_finding("f-012", operator_id="boss", note="deliberate naming choice")
            rec = get_finding_status("f-012")
            self.assertEqual(rec["note"], "deliberate naming choice")


# ---------------------------------------------------------------------------
# Suite 3 — PromoteToBaseline
# ---------------------------------------------------------------------------

class TestPromoteToBaseline(unittest.TestCase):

    def test_promote_to_baseline_requires_operator_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import promote_to_baseline
            with self.assertRaises(ValueError):
                promote_to_baseline("f-020", operator_id="")

    def test_promote_to_baseline_does_not_mutate_baseline_file(self) -> None:
        """CRITICAL: audit_baseline.py must never be modified automatically."""
        with _TempRuntime():
            from core.audit.drift_governance import promote_to_baseline
            import core.audit.audit_baseline as baseline_mod
            baseline_path = Path(baseline_mod.__file__)
            mtime_before = baseline_path.stat().st_mtime

            promote_to_baseline("f-021", operator_id="boss", note="naming drift")

            mtime_after = baseline_path.stat().st_mtime
            self.assertEqual(
                mtime_before, mtime_after,
                "promote_to_baseline() modified audit_baseline.py — invariant violated",
            )

    def test_promote_to_baseline_creates_proposal_artifact(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance import promote_to_baseline
            promote_to_baseline("f-022", operator_id="boss")
            proposals_path = rt / "state" / "drift_baseline_proposals.jsonl"
            self.assertTrue(proposals_path.exists())
            lines = proposals_path.read_text().strip().splitlines()
            self.assertGreater(len(lines), 0)
            proposal = json.loads(lines[-1])
            self.assertEqual(proposal["finding_id"], "f-022")
            self.assertEqual(proposal["status"], "PENDING_REVIEW")

    def test_promote_to_baseline_sets_finding_to_accepted(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import promote_to_baseline
            from core.audit.drift_governance_store import get_finding_status
            promote_to_baseline("f-023", operator_id="boss")
            rec = get_finding_status("f-023")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["status"], "ACCEPTED")

    def test_promote_to_baseline_proposal_has_required_fields(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance import promote_to_baseline
            promote_to_baseline("f-024", operator_id="boss", note="my note")
            lines = (rt / "state" / "drift_baseline_proposals.jsonl").read_text().strip().splitlines()
            proposal = json.loads(lines[-1])
            for field in ["ts", "proposal_id", "finding_id", "operator_id", "status", "instruction"]:
                self.assertIn(field, proposal, f"Proposal missing field '{field}'")

    def test_promote_result_has_proposal_id(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import promote_to_baseline
            result = promote_to_baseline("f-025", operator_id="boss")
            self.assertIn("proposal_id", result)
            self.assertEqual(result["status"], "PENDING_REVIEW")


# ---------------------------------------------------------------------------
# Suite 4 — GovStore
# ---------------------------------------------------------------------------

class TestGovStore(unittest.TestCase):

    def test_status_map_is_atomic_write(self) -> None:
        """Two sequential writes should leave a consistent final state."""
        with _TempRuntime() as rt:
            from core.audit.drift_governance_store import set_finding_status, load_finding_status
            set_finding_status("s-001", "ACCEPTED", "boss")
            set_finding_status("s-002", "ESCALATED", "boss")
            m = load_finding_status()
            self.assertIn("s-001", m)
            self.assertIn("s-002", m)
            self.assertEqual(m["s-001"]["status"], "ACCEPTED")
            self.assertEqual(m["s-002"]["status"], "ESCALATED")

    def test_governance_log_is_append_only(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance_store import append_governance_log
            append_governance_log({"ts": "t1", "action": "A"})
            append_governance_log({"ts": "t2", "action": "B"})
            lines = (rt / "state" / "drift_governance_log.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            # Both lines intact
            self.assertIn("A", lines[0])
            self.assertIn("B", lines[1])

    def test_list_finding_status_with_filter(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance_store import set_finding_status, list_finding_status
            set_finding_status("s-010", "ACCEPTED", "boss")
            set_finding_status("s-011", "ESCALATED", "boss")
            set_finding_status("s-012", "ACCEPTED", "boss")
            accepted = list_finding_status(status_filter="ACCEPTED")
            self.assertEqual(len(accepted), 2)
            for r in accepted:
                self.assertEqual(r["status"], "ACCEPTED")

    def test_get_finding_status_returns_none_for_unknown(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance_store import get_finding_status
            self.assertIsNone(get_finding_status("not-a-real-finding"))

    def test_load_finding_status_returns_empty_if_no_file(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance_store import load_finding_status
            result = load_finding_status()
            self.assertIsInstance(result, dict)
            self.assertEqual(result, {})

    def test_list_governance_log_returns_empty_if_no_file(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance_store import list_governance_log
            result = list_governance_log()
            self.assertIsInstance(result, list)
            self.assertEqual(result, [])

    def test_governance_log_entries_are_valid_json(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance import accept_finding, dismiss_finding
            accept_finding("s-020", operator_id="boss")
            dismiss_finding("s-020", operator_id="boss")
            lines = (rt / "state" / "drift_governance_log.jsonl").read_text().strip().splitlines()
            for i, line in enumerate(lines):
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    self.fail(f"Line {i} of drift_governance_log.jsonl is invalid JSON: {exc}")


# ---------------------------------------------------------------------------
# Suite 5 — APIGate
# ---------------------------------------------------------------------------

class TestAPIGate(unittest.TestCase):
    """All POST write endpoints must return 403 without operator_id."""

    def _mock_request(self, body: dict[str, Any]) -> MagicMock:
        async def _json() -> dict[str, Any]:
            return body

        req = MagicMock()
        req.json = _json
        req.headers = MagicMock()
        req.headers.get = lambda key, default="": ""
        return req

    def _run(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def test_accept_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_accept
            req = self._mock_request({"finding_id": "f-001"})  # no operator_id
            resp = self._run(drift_governance_accept(req))
            self.assertEqual(resp.status_code, 403)

    def test_dismiss_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_dismiss
            req = self._mock_request({"finding_id": "f-001"})
            resp = self._run(drift_governance_dismiss(req))
            self.assertEqual(resp.status_code, 403)

    def test_escalate_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_escalate
            req = self._mock_request({"finding_id": "f-001"})
            resp = self._run(drift_governance_escalate(req))
            self.assertEqual(resp.status_code, 403)

    def test_resolve_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_resolve
            req = self._mock_request({"finding_id": "f-001"})
            resp = self._run(drift_governance_resolve(req))
            self.assertEqual(resp.status_code, 403)

    def test_promote_to_baseline_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_promote
            req = self._mock_request({"finding_id": "f-001"})
            resp = self._run(drift_governance_promote(req))
            self.assertEqual(resp.status_code, 403)

    def test_accept_without_finding_id_returns_400(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_accept
            req = self._mock_request({"operator_id": "boss"})  # no finding_id
            resp = self._run(drift_governance_accept(req))
            self.assertEqual(resp.status_code, 400)

    def test_accept_with_valid_body_returns_200(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_accept
            req = self._mock_request({"finding_id": "f-accept-ok", "operator_id": "boss"})
            resp = self._run(drift_governance_accept(req))
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.body)
            self.assertTrue(body["ok"])


# ---------------------------------------------------------------------------
# Suite 6 — APIRead
# ---------------------------------------------------------------------------

class TestAPIRead(unittest.TestCase):

    def test_status_endpoint_returns_dict(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_status
            result = asyncio.run(drift_governance_status())
            self.assertIn("ok", result)
            self.assertIn("statuses", result)

    def test_log_endpoint_returns_list(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_log
            result = asyncio.run(drift_governance_log())
            self.assertIn("log", result)
            self.assertIsInstance(result["log"], list)

    def test_open_endpoint_returns_list(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_open
            result = asyncio.run(drift_governance_open())
            self.assertIn("open_findings", result)
            self.assertIsInstance(result["open_findings"], list)

    def test_proposals_endpoint_returns_list(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_governance import drift_governance_proposals
            result = asyncio.run(drift_governance_proposals())
            self.assertIn("proposals", result)
            self.assertIsInstance(result["proposals"], list)

    def test_log_endpoint_shows_append_only_history(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding, dismiss_finding
            from interface.operator.api_drift_governance import drift_governance_log
            accept_finding("f-log-1", operator_id="boss")
            dismiss_finding("f-log-1", operator_id="boss")
            result = asyncio.run(drift_governance_log())
            self.assertGreaterEqual(len(result["log"]), 2)


# ---------------------------------------------------------------------------
# Suite 7 — SafetyInvariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants(unittest.TestCase):

    def test_governance_does_not_modify_runtime_self_audit_json(self) -> None:
        with _TempRuntime() as rt:
            audit_path = _sentinel_file(rt, "runtime_self_audit.json",
                                        '{"sentinel": "must_not_change", "overall_verdict": "CONSISTENT"}')
            from core.audit.drift_governance import accept_finding
            accept_finding("f-safe-1", operator_id="boss")
            self.assertEqual(json.loads(audit_path.read_text())["sentinel"], "must_not_change")

    def test_governance_does_not_modify_drift_findings_jsonl(self) -> None:
        with _TempRuntime() as rt:
            findings_path = _sentinel_file(
                rt, "drift_findings.jsonl",
                '{"id": "f-safe-2", "drift_class": "naming_drift_only"}\n',
            )
            original = findings_path.read_text()
            from core.audit.drift_governance import accept_finding
            accept_finding("f-safe-2", operator_id="boss")
            self.assertEqual(findings_path.read_text(), original)

    def test_promote_to_baseline_does_not_write_baseline_code(self) -> None:
        """baseline proposals go to JSONL only — never to Python source files."""
        with _TempRuntime() as rt:
            import core.audit.audit_baseline as bmod
            baseline_path = Path(bmod.__file__)
            mtime_before = baseline_path.stat().st_mtime

            from core.audit.drift_governance import promote_to_baseline
            promote_to_baseline("f-safe-3", operator_id="boss")

            self.assertEqual(baseline_path.stat().st_mtime, mtime_before,
                             "promote_to_baseline() modified audit_baseline.py — invariant violated")

    def test_governance_own_outputs_limited_to_known_files(self) -> None:
        with _TempRuntime() as rt:
            state_d = rt / "state"
            before = set(p.name for p in state_d.iterdir())

            from core.audit.drift_governance import accept_finding, escalate_finding
            accept_finding("f-safe-4", operator_id="boss")
            escalate_finding("f-safe-4", operator_id="boss")

            after = set(p.name for p in state_d.iterdir())
            new_files = after - before
            allowed = {"drift_finding_status.json", "drift_governance_log.jsonl"}
            unexpected = new_files - allowed
            self.assertEqual(unexpected, set(),
                             f"Governance created unexpected files: {unexpected}")

    def test_dismissed_finding_history_preserved(self) -> None:
        """Dismissing a finding must not delete its governance history."""
        with _TempRuntime() as rt:
            from core.audit.drift_governance import accept_finding, dismiss_finding
            accept_finding("f-safe-5", operator_id="boss")
            dismiss_finding("f-safe-5", operator_id="boss", note="false positive")
            log_path = rt / "state" / "drift_governance_log.jsonl"
            lines = log_path.read_text().strip().splitlines()
            self.assertGreaterEqual(len(lines), 2,
                                    "Governance log lines were deleted after dismiss — invariant violated")


# ---------------------------------------------------------------------------
# Suite 8 — SmokeGovernance
# ---------------------------------------------------------------------------

class TestSmokeGovernance(unittest.TestCase):

    def test_full_lifecycle_open_accept_promote_resolve(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_governance import (
                accept_finding, promote_to_baseline, resolve_finding,
                list_governed_findings,
            )
            from core.audit.drift_governance_store import get_finding_status

            # Step 1: finding starts as OPEN (no record yet)
            self.assertIsNone(get_finding_status("lifecycle-001"))

            # Step 2: accept
            accept_finding("lifecycle-001", operator_id="boss", note="known naming drift")
            self.assertEqual(get_finding_status("lifecycle-001")["status"], "ACCEPTED")

            # Step 3: promote to baseline (creates proposal artifact, stays ACCEPTED)
            result = promote_to_baseline("lifecycle-001", operator_id="boss")
            self.assertIn("proposal_id", result)
            self.assertEqual(get_finding_status("lifecycle-001")["status"], "ACCEPTED")

            # Step 4: resolve
            resolve_finding("lifecycle-001", operator_id="boss", note="baseline updated in PR #400")
            self.assertEqual(get_finding_status("lifecycle-001")["status"], "RESOLVED")

            # Step 5: governance log has all events
            log_path = rt / "state" / "drift_governance_log.jsonl"
            log_entries = log_path.read_text().strip().splitlines()
            self.assertGreaterEqual(len(log_entries), 2)

            # Step 6: proposal artifact exists
            proposals = (rt / "state" / "drift_baseline_proposals.jsonl").read_text()
            self.assertIn("lifecycle-001", proposals)

    def test_escalate_and_resolve_lifecycle(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import escalate_finding, resolve_finding
            from core.audit.drift_governance_store import get_finding_status
            escalate_finding("lifecycle-002", operator_id="boss", note="real drift, needs PR")
            self.assertEqual(get_finding_status("lifecycle-002")["status"], "ESCALATED")
            resolve_finding("lifecycle-002", operator_id="boss", note="fixed in PR #401")
            self.assertEqual(get_finding_status("lifecycle-002")["status"], "RESOLVED")

    def test_status_query_after_multiple_findings(self) -> None:
        with _TempRuntime():
            from core.audit.drift_governance import accept_finding, escalate_finding
            from core.audit.drift_governance_store import list_finding_status
            accept_finding("m-001", operator_id="boss")
            escalate_finding("m-002", operator_id="boss")
            escalate_finding("m-003", operator_id="boss")
            accepted = list_finding_status(status_filter="ACCEPTED")
            escalated = list_finding_status(status_filter="ESCALATED")
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(escalated), 2)


if __name__ == "__main__":
    unittest.main()
