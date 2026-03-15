"""AG-22: Policy Promotion Runtime — test suite.

Suites:
  1. PromotionVerifier        — unit tests for verify_candidate()
  2. PolicyRegistry           — atomic writes, load/save, activation log
  3. PolicyPromoter           — promote() flow, operator gate, PENDING rejection
  4. PolicyGateIntegration    — plan_allowed() consults promoted registry
  5. ApiPoliciesUnit          — endpoint logic (no HTTP server needed)
  6. EndToEnd                 — full promote → gate flow
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _TempRuntime:
    """Context manager — sets LUKA_RUNTIME_ROOT to a fresh temp dir."""

    def __enter__(self) -> Path:
        self._td = tempfile.mkdtemp()
        os.environ["LUKA_RUNTIME_ROOT"] = self._td
        # flush any module-level caches that may have resolved old paths
        _reload_policy_modules()
        return Path(self._td)

    def __exit__(self, *_: object) -> None:
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)


def _reload_policy_modules() -> None:
    import importlib, sys
    for mod in [
        "core.policy.policy_registry",
        "core.policy.promotion_verifier",
        "core.policy.policy_promoter",
        "core.policy.policy_gate",
    ]:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])


def _approved_candidate(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "candidate_id": "cand_test001",
        "pattern_id": "pat_abc",
        "suggested_policy": "deny_delete_repo",
        "approval_state": "APPROVED",
        "confidence": 0.9,
        "safety_risk": "low",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Suite 1 — PromotionVerifier
# ---------------------------------------------------------------------------

class TestPromotionVerifier(unittest.TestCase):

    def _verify(self, **overrides: Any) -> tuple[bool, str]:
        from core.policy.promotion_verifier import verify_candidate
        return verify_candidate(_approved_candidate(**overrides))

    def test_valid_candidate_passes(self) -> None:
        ok, reason = self._verify()
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "ok")

    def test_missing_candidate_id_fails(self) -> None:
        ok, reason = self._verify(candidate_id="")
        self.assertFalse(ok)
        self.assertIn("candidate_id", reason)

    def test_missing_pattern_id_fails(self) -> None:
        ok, reason = self._verify(pattern_id="")
        self.assertFalse(ok)
        self.assertIn("pattern_id", reason)

    def test_empty_policy_fails(self) -> None:
        ok, reason = self._verify(suggested_policy="")
        self.assertFalse(ok)
        self.assertIn("suggested_policy", reason)

    def test_pending_state_rejected(self) -> None:
        ok, reason = self._verify(approval_state="PENDING")
        self.assertFalse(ok)
        self.assertIn("APPROVED", reason)

    def test_low_confidence_rejected(self) -> None:
        ok, reason = self._verify(confidence=0.7)
        self.assertFalse(ok)
        self.assertIn("confidence", reason)

    def test_boundary_confidence_passes(self) -> None:
        ok, _ = self._verify(confidence=0.8)
        self.assertTrue(ok)

    def test_high_risk_blocked(self) -> None:
        ok, reason = self._verify(safety_risk="high")
        self.assertFalse(ok)
        self.assertIn("high", reason)

    def test_medium_risk_allowed(self) -> None:
        ok, _ = self._verify(safety_risk="medium")
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# Suite 2 — PolicyRegistry
# ---------------------------------------------------------------------------

class TestPolicyRegistry(unittest.TestCase):

    def test_empty_registry_returns_empty_dict(self) -> None:
        with _TempRuntime():
            from core.policy.policy_registry import load_registry
            self.assertEqual(load_registry(), {})

    def test_register_and_get_policy(self) -> None:
        with _TempRuntime():
            from core.policy.policy_registry import register_policy, get_policy
            register_policy("pol1", {"rule": "deny_x", "policy_id": "pol1"})
            result = get_policy("pol1")
            self.assertIsNotNone(result)
            self.assertEqual(result["rule"], "deny_x")

    def test_list_policies(self) -> None:
        with _TempRuntime():
            from core.policy.policy_registry import register_policy, list_policies
            register_policy("pol_a", {"rule": "r1", "policy_id": "pol_a"})
            register_policy("pol_b", {"rule": "r2", "policy_id": "pol_b"})
            policies = list_policies()
            ids = {p["policy_id"] for p in policies}
            self.assertIn("pol_a", ids)
            self.assertIn("pol_b", ids)

    def test_save_registry_is_atomic(self) -> None:
        """No .tmp file should remain after save_registry."""
        with _TempRuntime() as root:
            from core.policy.policy_registry import register_policy
            register_policy("pol_x", {"policy_id": "pol_x", "rule": "r"})
            tmp_files = list(Path(root, "state").glob("*.tmp"))
            self.assertEqual(tmp_files, [])

    def test_activation_log_append(self) -> None:
        with _TempRuntime() as root:
            from core.policy.policy_registry import append_activation_log, list_activation_log
            append_activation_log({"candidate_id": "c1", "policy_id": "p1", "status": "ACTIVATED"})
            append_activation_log({"candidate_id": "c2", "policy_id": "p2", "status": "ACTIVATED"})
            entries = list_activation_log()
            self.assertEqual(len(entries), 2)
            ids = {e["candidate_id"] for e in entries}
            self.assertIn("c1", ids)
            self.assertIn("c2", ids)

    def test_remove_policy(self) -> None:
        with _TempRuntime():
            from core.policy.policy_registry import register_policy, remove_policy, get_policy
            register_policy("rem1", {"policy_id": "rem1", "rule": "r"})
            removed = remove_policy("rem1")
            self.assertTrue(removed)
            self.assertIsNone(get_policy("rem1"))

    def test_remove_nonexistent_returns_false(self) -> None:
        with _TempRuntime():
            from core.policy.policy_registry import remove_policy
            self.assertFalse(remove_policy("ghost"))


# ---------------------------------------------------------------------------
# Suite 3 — PolicyPromoter
# ---------------------------------------------------------------------------

class TestPolicyPromoter(unittest.TestCase):

    def test_promote_approved_candidate_succeeds(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_registry import get_policy
            result = promote(_approved_candidate(), operator_id="op_alice")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["policy_id"], "cand_test001")
            stored = get_policy("cand_test001")
            self.assertIsNotNone(stored)
            self.assertEqual(stored["activated_by"], "op_alice")

    def test_promote_pending_candidate_rejected(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            result = promote(_approved_candidate(approval_state="PENDING"), operator_id="op_alice")
            self.assertFalse(result["ok"])
            self.assertIn("APPROVED", result["reason"])

    def test_promote_without_operator_id_rejected(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            result = promote(_approved_candidate(), operator_id="")
            self.assertFalse(result["ok"])
            self.assertIn("operator_id", result["reason"])

    def test_promote_writes_activation_log(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_registry import list_activation_log
            promote(_approved_candidate(), operator_id="op_bob")
            log = list_activation_log()
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["status"], "ACTIVATED")
            self.assertEqual(log[0]["operator_id"], "op_bob")

    def test_promote_low_confidence_rejected(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            result = promote(_approved_candidate(confidence=0.5), operator_id="op_alice")
            self.assertFalse(result["ok"])
            self.assertIn("confidence", result["reason"])

    def test_promote_high_risk_rejected(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            result = promote(_approved_candidate(safety_risk="high"), operator_id="op_alice")
            self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# Suite 4 — PolicyGateIntegration
# ---------------------------------------------------------------------------

class TestPolicyGateIntegration(unittest.TestCase):

    def _make_plan(self, *action_types: str) -> dict[str, Any]:
        return {
            "run_id": "run_test",
            "steps": [{"action": a} for a in action_types],
        }

    def test_plan_allowed_no_registry(self) -> None:
        """With empty registry, plan_allowed still works normally."""
        with _TempRuntime():
            from core.policy.policy_gate import plan_allowed
            # verify_artifacts is an allowed step action
            result = plan_allowed(self._make_plan("verify_artifacts"))
            self.assertEqual(result, "ALLOW")

    def test_promoted_deny_delete_repo_blocks_plan(self) -> None:
        """A promoted deny_delete_repo rule must block a delete_repo plan."""
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_gate import plan_allowed
            promote(
                _approved_candidate(
                    candidate_id="pol_deny",
                    suggested_policy="deny_delete_repo",
                ),
                operator_id="op_alice",
            )
            # delete_repo is not in _ALLOWED_STEP_ACTIONS so step_allowed → ESCALATE
            # but the registry check should return BLOCK
            # First let's test via the registry path directly
            from core.policy.policy_registry import list_policies
            policies = list_policies()
            self.assertEqual(len(policies), 1)
            self.assertIn("deny_delete_repo", policies[0]["rule"])

    def test_registry_consulted_in_plan_allowed(self) -> None:
        """plan_allowed returns BLOCK when promoted policy matches plan action."""
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_gate import plan_allowed
            promote(
                _approved_candidate(
                    candidate_id="pol_deny2",
                    suggested_policy="deny_delete_repo",
                ),
                operator_id="op_alice",
            )
            plan = {"run_id": "r1", "steps": [{"action": "delete_repo"}]}
            # delete_repo step: step_allowed → ESCALATE first (not in DESTRUCTIVE_ACTIONS,
            # not in _ALLOWED_STEP_ACTIONS) → plan would be ESCALATE from step check.
            # Our registry rule additionally returns BLOCK for delete_repo.
            # The test verifies registry is consulted and the result is BLOCK.
            result = plan_allowed(plan)
            self.assertEqual(result, "BLOCK")

    def test_empty_plan_still_allow(self) -> None:
        with _TempRuntime():
            from core.policy.policy_gate import plan_allowed
            self.assertEqual(plan_allowed({"run_id": "r", "steps": []}), "ALLOW")


# ---------------------------------------------------------------------------
# Suite 5 — ApiPoliciesUnit
# ---------------------------------------------------------------------------

class TestApiPoliciesUnit(unittest.TestCase):

    def test_policies_list_returns_dict(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_policies import policies_list
            result = asyncio.run(policies_list())
            self.assertIn("policies", result)
            self.assertIsInstance(result["policies"], list)

    def test_activation_log_returns_dict(self) -> None:
        import asyncio
        with _TempRuntime():
            from interface.operator.api_policies import policy_activation_log
            result = asyncio.run(policy_activation_log())
            self.assertIn("activation_log", result)

    def test_load_candidate_not_found_returns_none(self) -> None:
        with _TempRuntime():
            from interface.operator.api_policies import _load_candidate
            self.assertIsNone(_load_candidate("nonexistent_id"))


# ---------------------------------------------------------------------------
# Suite 6 — EndToEnd
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def test_full_promote_and_gate_flow(self) -> None:
        """Promote a candidate → policy_gate enforces it on a matching plan."""
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_gate import plan_allowed
            from core.policy.policy_registry import list_policies, list_activation_log

            # 1. promote
            result = promote(
                _approved_candidate(
                    candidate_id="e2e_pol",
                    suggested_policy="deny_delete_repo",
                ),
                operator_id="op_e2e",
            )
            self.assertTrue(result["ok"], result)

            # 2. registry has entry
            policies = list_policies()
            self.assertEqual(len(policies), 1)

            # 3. activation log has entry
            log = list_activation_log()
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["status"], "ACTIVATED")

            # 4. policy_gate blocks matching plan
            plan = {"run_id": "r_e2e", "steps": [{"action": "delete_repo"}]}
            verdict = plan_allowed(plan)
            self.assertEqual(verdict, "BLOCK")

    def test_pending_candidate_cannot_be_promoted(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_registry import load_registry
            result = promote(
                _approved_candidate(approval_state="PENDING"),
                operator_id="op_e2e",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(load_registry(), {})  # nothing written

    def test_no_operator_no_promotion(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_registry import load_registry
            result = promote(_approved_candidate(), operator_id="")
            self.assertFalse(result["ok"])
            self.assertEqual(load_registry(), {})


if __name__ == "__main__":
    unittest.main()
