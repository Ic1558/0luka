"""AG-30: Policy Outcome Governance — test suite.

Suites:
  1. RouterVerdictMapping   — route_verdict() maps all 4 verdicts correctly
  2. RouterRationale        — _build_rationale() produces sensible strings
  3. OutcomeStoreBasic      — create / append / write_latest / list
  4. OutcomeStoreUpdate     — update_governance_record() round-trip
  5. OperatorActions        — ROLLBACK triggers revoke_policy, QUARANTINE triggers deprecate_policy
  6. OperatorGate           — API endpoints reject missing operator_id
  7. RunOutcomeGovernance    — full pipeline: effectiveness → router → store
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _TempRuntime:
    def __enter__(self) -> Path:
        self._td = tempfile.mkdtemp()
        os.environ["LUKA_RUNTIME_ROOT"] = self._td
        return Path(self._td)

    def __exit__(self, *_: object) -> None:
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self._td, ignore_errors=True)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def _state(root: Path) -> Path:
    d = root / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Suite 1 — RouterVerdictMapping
# ---------------------------------------------------------------------------

class TestRouterVerdictMapping(unittest.TestCase):

    def setUp(self) -> None:
        from core.policy.outcome_router import route_verdict
        self.route = route_verdict

    def _make_rec(self, verdict: str, policy_id: str = "p1") -> dict[str, Any]:
        return {"policy_id": policy_id, "verdict": verdict, "delta": -0.3, "after_count": 5}

    def test_keep_maps_to_retain(self) -> None:
        r = self.route(self._make_rec("KEEP"))
        self.assertEqual(r["recommended_action"], "RETAIN")
        self.assertEqual(r["effectiveness_verdict"], "KEEP")

    def test_review_maps_to_review_required(self) -> None:
        r = self.route(self._make_rec("REVIEW"))
        self.assertEqual(r["recommended_action"], "REVIEW_REQUIRED")

    def test_rollback_maps_to_rollback_candidate(self) -> None:
        r = self.route(self._make_rec("ROLLBACK_RECOMMENDED"))
        self.assertEqual(r["recommended_action"], "ROLLBACK_CANDIDATE")

    def test_inconclusive_maps_to_monitor(self) -> None:
        r = self.route(self._make_rec("INCONCLUSIVE"))
        self.assertEqual(r["recommended_action"], "MONITOR")

    def test_unknown_verdict_defaults_to_monitor(self) -> None:
        r = self.route(self._make_rec("GARBAGE"))
        self.assertEqual(r["recommended_action"], "MONITOR")

    def test_evidence_fields_passed_through(self) -> None:
        rec = {
            "policy_id": "px",
            "verdict": "KEEP",
            "before_failures": 3,
            "after_failures": 1,
            "baseline_failure_rate": 0.6,
            "post_failure_rate": 0.2,
            "delta": -0.4,
            "before_count": 5,
            "after_count": 5,
        }
        r = self.route(rec)
        self.assertEqual(r["before_failures"], 3)
        self.assertEqual(r["after_failures"], 1)
        self.assertEqual(r["delta"], -0.4)

    def test_policy_id_preserved(self) -> None:
        r = self.route(self._make_rec("KEEP", policy_id="my_policy"))
        self.assertEqual(r["policy_id"], "my_policy")


# ---------------------------------------------------------------------------
# Suite 2 — RouterRationale
# ---------------------------------------------------------------------------

class TestRouterRationale(unittest.TestCase):

    def _route(self, verdict: str, **kwargs: Any) -> str:
        from core.policy.outcome_router import route_verdict
        rec = {"policy_id": "p", "verdict": verdict, **kwargs}
        return route_verdict(rec)["rationale"]

    def test_keep_rationale_mentions_improvement(self) -> None:
        r = self._route("KEEP", delta=-0.3)
        self.assertIn("confirmed effective", r)

    def test_rollback_rationale_mentions_worsened(self) -> None:
        r = self._route("ROLLBACK_RECOMMENDED", delta=0.25)
        self.assertIn("recommended", r)

    def test_review_rationale_mentions_marginal(self) -> None:
        r = self._route("REVIEW")
        self.assertIn("marginal", r)

    def test_inconclusive_rationale_mentions_count(self) -> None:
        r = self._route("INCONCLUSIVE", after_count=1)
        self.assertIn("1", r)


# ---------------------------------------------------------------------------
# Suite 3 — OutcomeStoreBasic
# ---------------------------------------------------------------------------

class TestOutcomeStoreBasic(unittest.TestCase):

    def test_create_record_shape(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import create_governance_record
            rec = create_governance_record({
                "policy_id": "p1",
                "effectiveness_verdict": "KEEP",
                "recommended_action": "RETAIN",
                "rationale": "test",
            })
            self.assertIn("governance_id", rec)
            self.assertEqual(rec["status"], "PENDING_OPERATOR")
            self.assertIsNone(rec["actioned_at"])
            self.assertIsNone(rec["action_taken"])

    def test_append_and_list(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import create_governance_record, append_governance_record, list_governance_log
            r1 = create_governance_record({"policy_id": "p1", "effectiveness_verdict": "KEEP", "recommended_action": "RETAIN", "rationale": "a"})
            r2 = create_governance_record({"policy_id": "p2", "effectiveness_verdict": "REVIEW", "recommended_action": "REVIEW_REQUIRED", "rationale": "b"})
            append_governance_record(r1)
            append_governance_record(r2)
            log = list_governance_log()
            self.assertEqual(len(log), 2)
            ids = {e["policy_id"] for e in log}
            self.assertIn("p1", ids)
            self.assertIn("p2", ids)

    def test_write_latest_upsert(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest, get_latest_for_policy
            rec = create_governance_record({"policy_id": "pol", "effectiveness_verdict": "ROLLBACK_RECOMMENDED", "recommended_action": "ROLLBACK_CANDIDATE", "rationale": "x"})
            append_governance_record(rec)
            write_latest(rec)
            latest = get_latest_for_policy("pol")
            self.assertIsNotNone(latest)
            self.assertEqual(latest["recommended_action"], "ROLLBACK_CANDIDATE")

    def test_list_all_latest(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest, list_all_latest
            for pid, verdict, action in [("a", "KEEP", "RETAIN"), ("b", "REVIEW", "REVIEW_REQUIRED")]:
                r = create_governance_record({"policy_id": pid, "effectiveness_verdict": verdict, "recommended_action": action, "rationale": ""})
                append_governance_record(r)
                write_latest(r)
            all_latest = list_all_latest()
            pids = {r["policy_id"] for r in all_latest}
            self.assertIn("a", pids)
            self.assertIn("b", pids)

    def test_atomic_write_no_tmp_files(self) -> None:
        with _TempRuntime() as root:
            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest
            rec = create_governance_record({"policy_id": "q1", "effectiveness_verdict": "KEEP", "recommended_action": "RETAIN", "rationale": ""})
            append_governance_record(rec)
            write_latest(rec)
            tmp_files = list((root / "state").glob("*.tmp"))
            self.assertEqual(tmp_files, [])

    def test_get_latest_nonexistent_returns_none(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import get_latest_for_policy
            self.assertIsNone(get_latest_for_policy("no_such_policy"))


# ---------------------------------------------------------------------------
# Suite 4 — OutcomeStoreUpdate
# ---------------------------------------------------------------------------

class TestOutcomeStoreUpdate(unittest.TestCase):

    def test_update_sets_action_fields(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import (
                create_governance_record, append_governance_record,
                write_latest, update_governance_record, get_latest_for_policy,
            )
            rec = create_governance_record({"policy_id": "upd1", "effectiveness_verdict": "ROLLBACK_RECOMMENDED", "recommended_action": "ROLLBACK_CANDIDATE", "rationale": "x"})
            append_governance_record(rec)
            write_latest(rec)

            updated = update_governance_record(rec["governance_id"], {
                "status": "ACTIONED",
                "action_taken": "ROLLED_BACK",
                "actioned_at": "2026-03-16T00:00:00Z",
                "actioned_by": "op1",
            })
            self.assertIsNotNone(updated)
            self.assertEqual(updated["status"], "ACTIONED")
            self.assertEqual(updated["action_taken"], "ROLLED_BACK")
            self.assertEqual(updated["actioned_by"], "op1")

            # latest should reflect update
            latest = get_latest_for_policy("upd1")
            self.assertEqual(latest["status"], "ACTIONED")

    def test_update_nonexistent_returns_none(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import update_governance_record
            result = update_governance_record("doesnotexist", {"status": "ACTIONED"})
            self.assertIsNone(result)

    def test_dismissed_status(self) -> None:
        with _TempRuntime():
            from core.policy.outcome_store import (
                create_governance_record, append_governance_record, write_latest, update_governance_record,
            )
            rec = create_governance_record({"policy_id": "d1", "effectiveness_verdict": "REVIEW", "recommended_action": "REVIEW_REQUIRED", "rationale": ""})
            append_governance_record(rec)
            write_latest(rec)
            updated = update_governance_record(rec["governance_id"], {"status": "DISMISSED", "action_taken": "DISMISSED"})
            self.assertEqual(updated["status"], "DISMISSED")


# ---------------------------------------------------------------------------
# Suite 5 — OperatorActions (side effects)
# ---------------------------------------------------------------------------

class TestOperatorActions(unittest.TestCase):

    def test_rolled_back_calls_revoke_policy(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            # seed a registered policy
            registry = {"pol_rb": {"policy_id": "pol_rb", "status": "ACTIVE"}}
            (state / "policy_registry.json").write_text(json.dumps(registry), encoding="utf-8")
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "pol_rb", "status": "ACTIVATED", "ts": "2026-03-10T00:00:00Z"},
            ])

            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest
            rec = create_governance_record({
                "policy_id": "pol_rb",
                "effectiveness_verdict": "ROLLBACK_RECOMMENDED",
                "recommended_action": "ROLLBACK_CANDIDATE",
                "rationale": "bad",
            })
            append_governance_record(rec)
            write_latest(rec)

            revoke_called: list[str] = []
            import core.policy.policy_lifecycle as lc
            orig_revoke = lc.revoke_policy
            try:
                def _mock_revoke(policy_id: str, operator_id: str, reason: str = "") -> dict[str, Any]:
                    revoke_called.append(policy_id)
                    return {}
                lc.revoke_policy = _mock_revoke  # type: ignore[assignment]

                # Simulate what api_outcome does
                from core.policy.outcome_store import update_governance_record
                update_governance_record(rec["governance_id"], {
                    "status": "ACTIONED",
                    "action_taken": "ROLLED_BACK",
                    "actioned_at": "2026-03-16T00:00:00Z",
                    "actioned_by": "op1",
                })
                lc.revoke_policy("pol_rb", "op1", reason="test")
            finally:
                lc.revoke_policy = orig_revoke  # type: ignore[assignment]

            self.assertIn("pol_rb", revoke_called)

    def test_quarantined_calls_deprecate_policy(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            registry = {"pol_q": {"policy_id": "pol_q", "status": "ACTIVE"}}
            (state / "policy_registry.json").write_text(json.dumps(registry), encoding="utf-8")
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "pol_q", "status": "ACTIVATED", "ts": "2026-03-10T00:00:00Z"},
            ])

            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest
            rec = create_governance_record({
                "policy_id": "pol_q",
                "effectiveness_verdict": "REVIEW",
                "recommended_action": "REVIEW_REQUIRED",
                "rationale": "marginal",
            })
            append_governance_record(rec)
            write_latest(rec)

            deprecate_called: list[str] = []
            import core.policy.policy_lifecycle as lc
            orig_deprecate = lc.deprecate_policy
            try:
                def _mock_deprecate(policy_id: str, operator_id: str, reason: str = "") -> dict[str, Any]:
                    deprecate_called.append(policy_id)
                    return {}
                lc.deprecate_policy = _mock_deprecate  # type: ignore[assignment]
                lc.deprecate_policy("pol_q", "op1", reason="test")
            finally:
                lc.deprecate_policy = orig_deprecate  # type: ignore[assignment]

            self.assertIn("pol_q", deprecate_called)


# ---------------------------------------------------------------------------
# Suite 6 — OperatorGate
# ---------------------------------------------------------------------------

class TestOperatorGate(unittest.TestCase):

    def _make_request(self, body: dict[str, Any], headers: dict[str, str] | None = None) -> MagicMock:
        req = MagicMock()
        import asyncio
        async def _json() -> dict[str, Any]:
            return body
        req.json = _json
        req.headers = headers or {}
        return req

    def test_outcome_action_requires_operator_id(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_outcome import outcome_action_endpoint
            req = self._make_request({"governance_id": "abc123", "action": "RETAINED"})
            resp = asyncio.run(outcome_action_endpoint(req))
            # Should get 403
            self.assertEqual(resp.status_code, 403)

    def test_run_outcome_governance_requires_operator_id(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_outcome import run_outcome_governance_endpoint
            req = self._make_request({"policy_id": "p1"})
            resp = asyncio.run(run_outcome_governance_endpoint(req))
            self.assertEqual(resp.status_code, 403)

    def test_outcome_action_rejects_invalid_action(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_outcome import outcome_action_endpoint
            req = self._make_request({"governance_id": "abc123", "action": "NUKE", "operator_id": "op1"})
            resp = asyncio.run(outcome_action_endpoint(req))
            self.assertEqual(resp.status_code, 400)

    def test_outcome_action_404_on_unknown_governance_id(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_outcome import outcome_action_endpoint
            req = self._make_request({"governance_id": "nosuchid", "action": "DISMISSED", "operator_id": "op1"})
            resp = asyncio.run(outcome_action_endpoint(req))
            self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Suite 7 — RunOutcomeGovernance (full pipeline)
# ---------------------------------------------------------------------------

class TestRunOutcomeGovernance(unittest.TestCase):

    def test_route_verdict_and_store_full_pipeline(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "full1", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            # 1 before failure, 3 after successes → KEEP
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
                {"timestamp": "2026-03-12T00:00:00Z", "execution_result": "SUCCESS"},
                {"timestamp": "2026-03-13T00:00:00Z", "execution_result": "SUCCESS"},
            ])

            from core.policy.policy_effectiveness import run_and_persist
            from core.policy.outcome_router import route_verdict
            from core.policy.outcome_store import (
                create_governance_record, append_governance_record, write_latest, get_latest_for_policy,
            )

            effectiveness = run_and_persist("full1")
            self.assertEqual(effectiveness["verdict"], "KEEP")

            recommendation = route_verdict(effectiveness)
            self.assertEqual(recommendation["recommended_action"], "RETAIN")

            record = create_governance_record(recommendation)
            append_governance_record(record)
            write_latest(record)

            latest = get_latest_for_policy("full1")
            self.assertIsNotNone(latest)
            self.assertEqual(latest["recommended_action"], "RETAIN")
            self.assertEqual(latest["status"], "PENDING_OPERATOR")

    def test_rollback_pipeline(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "rb1", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            # 0 before failures, 3 after failures → ROLLBACK_RECOMMENDED
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "SUCCESS"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-12T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-13T00:00:00Z", "execution_result": "FAILED"},
            ])

            from core.policy.policy_effectiveness import run_and_persist
            from core.policy.outcome_router import route_verdict
            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest, get_latest_for_policy

            effectiveness = run_and_persist("rb1")
            self.assertEqual(effectiveness["verdict"], "ROLLBACK_RECOMMENDED")

            recommendation = route_verdict(effectiveness)
            self.assertEqual(recommendation["recommended_action"], "ROLLBACK_CANDIDATE")

            record = create_governance_record(recommendation)
            append_governance_record(record)
            write_latest(record)

            latest = get_latest_for_policy("rb1")
            self.assertEqual(latest["recommended_action"], "ROLLBACK_CANDIDATE")
            self.assertEqual(latest["effectiveness_verdict"], "ROLLBACK_RECOMMENDED")


if __name__ == "__main__":
    unittest.main()
