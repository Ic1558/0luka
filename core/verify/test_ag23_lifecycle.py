"""AG-23: Policy Lifecycle & Governance — test suite.

Suites:
  1. Revoke         — revoke_policy() transitions ACTIVE→REVOKED
  2. Deprecate      — deprecate_policy() transitions ACTIVE→DEPRECATED
  3. Supersede      — supersede_policy() ACTIVE→SUPERSEDED + pointer
  4. TTLExpiry      — expire_stale_policies() marks EXPIRED by age
  5. GateFiltering  — plan_allowed() only enforces ACTIVE policies
  6. EndToEnd       — full promote → lifecycle transition → gate behaviour
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _TempRuntime:
    def __enter__(self) -> Path:
        self._td = tempfile.mkdtemp()
        os.environ["LUKA_RUNTIME_ROOT"] = self._td
        _reload()
        return Path(self._td)

    def __exit__(self, *_: object) -> None:
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self._td, ignore_errors=True)


def _reload() -> None:
    import importlib, sys
    for mod in [
        "core.policy.policy_registry",
        "core.policy.policy_lifecycle",
        "core.policy.policy_gate",
    ]:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])


def _seed_active_policy(policy_id: str = "pol_active", rule: str = "deny_delete_repo") -> dict[str, Any]:
    """Insert an ACTIVE policy directly into the registry."""
    from core.policy.policy_registry import register_policy
    record: dict[str, Any] = {
        "policy_id": policy_id,
        "rule": rule,
        "source": "test",
        "confidence": 0.9,
        "safety_risk": "low",
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "activated_by": "test_operator",
        "status": "ACTIVE",
    }
    register_policy(policy_id, record)
    return record


# ---------------------------------------------------------------------------
# Suite 1 — Revoke
# ---------------------------------------------------------------------------

class TestRevoke(unittest.TestCase):

    def test_revoke_active_policy_succeeds(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_r1")
            from core.policy.policy_lifecycle import revoke_policy
            result = revoke_policy("pol_r1", "op_alice", reason="security issue")
            self.assertTrue(result["ok"], result)

    def test_revoked_policy_status_updated(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_r2")
            from core.policy.policy_lifecycle import revoke_policy
            from core.policy.policy_registry import get_policy
            revoke_policy("pol_r2", "op_alice")
            p = get_policy("pol_r2")
            self.assertEqual(p["status"], "REVOKED")
            self.assertIn("revoked_at", p)
            self.assertEqual(p["revoked_by"], "op_alice")

    def test_revoke_logs_event(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_r3")
            from core.policy.policy_lifecycle import revoke_policy
            from core.policy.policy_registry import list_activation_log
            revoke_policy("pol_r3", "op_alice", reason="test")
            log = list_activation_log()
            revoke_entries = [e for e in log if e.get("status") == "REVOKED"]
            self.assertEqual(len(revoke_entries), 1)
            self.assertEqual(revoke_entries[0]["policy_id"], "pol_r3")

    def test_revoke_nonexistent_fails(self) -> None:
        with _TempRuntime():
            from core.policy.policy_lifecycle import revoke_policy
            result = revoke_policy("ghost", "op_alice")
            self.assertFalse(result["ok"])
            self.assertIn("not found", result["reason"])

    def test_revoke_without_operator_fails(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_r4")
            from core.policy.policy_lifecycle import revoke_policy
            result = revoke_policy("pol_r4", "")
            self.assertFalse(result["ok"])
            self.assertIn("operator_id", result["reason"])


# ---------------------------------------------------------------------------
# Suite 2 — Deprecate
# ---------------------------------------------------------------------------

class TestDeprecate(unittest.TestCase):

    def test_deprecate_active_policy_succeeds(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_d1")
            from core.policy.policy_lifecycle import deprecate_policy
            result = deprecate_policy("pol_d1", "op_bob")
            self.assertTrue(result["ok"], result)

    def test_deprecated_policy_status_updated(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_d2")
            from core.policy.policy_lifecycle import deprecate_policy
            from core.policy.policy_registry import get_policy
            deprecate_policy("pol_d2", "op_bob")
            p = get_policy("pol_d2")
            self.assertEqual(p["status"], "DEPRECATED")
            self.assertIn("deprecated_at", p)

    def test_deprecate_logs_event(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_d3")
            from core.policy.policy_lifecycle import deprecate_policy
            from core.policy.policy_registry import list_activation_log
            deprecate_policy("pol_d3", "op_bob")
            log = list_activation_log()
            dep_entries = [e for e in log if e.get("status") == "DEPRECATED"]
            self.assertEqual(len(dep_entries), 1)

    def test_deprecate_nonexistent_fails(self) -> None:
        with _TempRuntime():
            from core.policy.policy_lifecycle import deprecate_policy
            result = deprecate_policy("ghost", "op_bob")
            self.assertFalse(result["ok"])

    def test_deprecate_without_operator_fails(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_d4")
            from core.policy.policy_lifecycle import deprecate_policy
            result = deprecate_policy("pol_d4", "")
            self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# Suite 3 — Supersede
# ---------------------------------------------------------------------------

class TestSupersede(unittest.TestCase):

    def test_supersede_succeeds_both_exist(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_old", rule="deny_delete_repo")
            _seed_active_policy("pol_new", rule="deny_delete_repo_v2")
            from core.policy.policy_lifecycle import supersede_policy
            result = supersede_policy("pol_old", "pol_new", "op_charlie")
            self.assertTrue(result["ok"], result)

    def test_superseded_policy_has_pointer(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_s1")
            _seed_active_policy("pol_s2")
            from core.policy.policy_lifecycle import supersede_policy
            from core.policy.policy_registry import get_policy
            supersede_policy("pol_s1", "pol_s2", "op_charlie")
            p = get_policy("pol_s1")
            self.assertEqual(p["status"], "SUPERSEDED")
            self.assertEqual(p["superseded_by"], "pol_s2")

    def test_supersede_logs_event(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_s3")
            _seed_active_policy("pol_s4")
            from core.policy.policy_lifecycle import supersede_policy
            from core.policy.policy_registry import list_activation_log
            supersede_policy("pol_s3", "pol_s4", "op_charlie")
            log = list_activation_log()
            sup_entries = [e for e in log if e.get("status") == "SUPERSEDED"]
            self.assertEqual(len(sup_entries), 1)
            self.assertEqual(sup_entries[0]["superseded_by"], "pol_s4")

    def test_supersede_missing_old_fails(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_s5")
            from core.policy.policy_lifecycle import supersede_policy
            result = supersede_policy("ghost", "pol_s5", "op_charlie")
            self.assertFalse(result["ok"])

    def test_supersede_missing_new_fails(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_s6")
            from core.policy.policy_lifecycle import supersede_policy
            result = supersede_policy("pol_s6", "ghost", "op_charlie")
            self.assertFalse(result["ok"])

    def test_supersede_without_operator_fails(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_s7")
            _seed_active_policy("pol_s8")
            from core.policy.policy_lifecycle import supersede_policy
            result = supersede_policy("pol_s7", "pol_s8", "")
            self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# Suite 4 — TTL Expiry
# ---------------------------------------------------------------------------

class TestTTLExpiry(unittest.TestCase):

    def _seed_old_policy(self, policy_id: str, age_seconds: int) -> None:
        from core.policy.policy_registry import register_policy
        old_ts = time.gmtime(time.time() - age_seconds)
        record = {
            "policy_id": policy_id,
            "rule": "test_rule",
            "source": "test",
            "confidence": 0.9,
            "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", old_ts),
            "activated_by": "test_op",
            "status": "ACTIVE",
        }
        register_policy(policy_id, record)

    def test_no_expiry_when_ttl_zero(self) -> None:
        with _TempRuntime():
            self._seed_old_policy("pol_e1", age_seconds=9999)
            from core.policy.policy_lifecycle import expire_stale_policies
            expired = expire_stale_policies(ttl_seconds=0)
            self.assertEqual(expired, [])

    def test_expires_old_policy(self) -> None:
        with _TempRuntime():
            self._seed_old_policy("pol_e2", age_seconds=7200)
            from core.policy.policy_lifecycle import expire_stale_policies
            from core.policy.policy_registry import get_policy
            expired = expire_stale_policies(ttl_seconds=3600)
            self.assertIn("pol_e2", expired)
            p = get_policy("pol_e2")
            self.assertEqual(p["status"], "EXPIRED")

    def test_does_not_expire_fresh_policy(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_e3")  # just activated
            from core.policy.policy_lifecycle import expire_stale_policies
            expired = expire_stale_policies(ttl_seconds=3600)
            self.assertNotIn("pol_e3", expired)

    def test_expiry_logs_event(self) -> None:
        with _TempRuntime():
            self._seed_old_policy("pol_e4", age_seconds=7200)
            from core.policy.policy_lifecycle import expire_stale_policies
            from core.policy.policy_registry import list_activation_log
            expire_stale_policies(ttl_seconds=3600)
            log = list_activation_log()
            exp_entries = [e for e in log if e.get("status") == "EXPIRED"]
            self.assertEqual(len(exp_entries), 1)

    def test_idempotent_expiry(self) -> None:
        """Running expire twice does not double-log or error."""
        with _TempRuntime():
            self._seed_old_policy("pol_e5", age_seconds=7200)
            from core.policy.policy_lifecycle import expire_stale_policies
            from core.policy.policy_registry import list_activation_log
            expire_stale_policies(ttl_seconds=3600)
            expire_stale_policies(ttl_seconds=3600)
            exp_entries = [e for e in list_activation_log() if e.get("status") == "EXPIRED"]
            self.assertEqual(len(exp_entries), 1)  # only logged once (already EXPIRED on 2nd run)


# ---------------------------------------------------------------------------
# Suite 5 — GateFiltering
# ---------------------------------------------------------------------------

class TestGateFiltering(unittest.TestCase):

    def _plan_with_action(self, action: str) -> dict[str, Any]:
        return {"run_id": "r_test", "steps": [{"action": action}]}

    def test_active_policy_blocks_matching_plan(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_g1", rule="deny_delete_repo")
            from core.policy.policy_gate import plan_allowed
            result = plan_allowed(self._plan_with_action("delete_repo"))
            self.assertEqual(result, "BLOCK")

    def test_revoked_policy_does_not_block(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_g2", rule="deny_delete_repo")
            from core.policy.policy_lifecycle import revoke_policy
            from core.policy.policy_gate import plan_allowed
            revoke_policy("pol_g2", "op_test")
            # After revoke, policy is no longer active — should not block
            result = plan_allowed(self._plan_with_action("delete_repo"))
            # delete_repo is not in DESTRUCTIVE_ACTIONS or _ALLOWED_STEP_ACTIONS → ESCALATE
            self.assertNotEqual(result, "BLOCK")

    def test_deprecated_policy_does_not_block(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_g3", rule="deny_delete_repo")
            from core.policy.policy_lifecycle import deprecate_policy
            from core.policy.policy_gate import plan_allowed
            deprecate_policy("pol_g3", "op_test")
            result = plan_allowed(self._plan_with_action("delete_repo"))
            self.assertNotEqual(result, "BLOCK")

    def test_superseded_policy_does_not_block(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_g4", rule="deny_delete_repo")
            # pol_g5 has a completely different rule — no deny_delete_repo substring
            _seed_active_policy("pol_g5", rule="deny_force_push")
            from core.policy.policy_lifecycle import supersede_policy
            from core.policy.policy_gate import plan_allowed
            supersede_policy("pol_g4", "pol_g5", "op_test")
            # pol_g4 is SUPERSEDED → not enforced; pol_g5 rule deny_force_push → no match
            # delete_repo plan should not be BLOCKed by registry
            result = plan_allowed(self._plan_with_action("delete_repo"))
            self.assertNotEqual(result, "BLOCK")

    def test_list_active_excludes_inactive(self) -> None:
        with _TempRuntime():
            _seed_active_policy("pol_g6")
            _seed_active_policy("pol_g7")
            from core.policy.policy_lifecycle import revoke_policy, list_active_policies
            revoke_policy("pol_g6", "op_test")
            active = list_active_policies()
            active_ids = {p["policy_id"] for p in active}
            self.assertNotIn("pol_g6", active_ids)
            self.assertIn("pol_g7", active_ids)


# ---------------------------------------------------------------------------
# Suite 6 — EndToEnd
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def test_promote_revoke_gate_flow(self) -> None:
        """Promote → gate blocks → revoke → gate no longer blocks."""
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_lifecycle import revoke_policy
            from core.policy.policy_gate import plan_allowed

            candidate = {
                "candidate_id": "e2e_lc",
                "pattern_id": "pat_x",
                "suggested_policy": "deny_delete_repo",
                "approval_state": "APPROVED",
                "confidence": 0.9,
                "safety_risk": "low",
            }
            plan = {"run_id": "r_e2e", "steps": [{"action": "delete_repo"}]}

            # Promote → should block
            promote(candidate, "op_alice")
            self.assertEqual(plan_allowed(plan), "BLOCK")

            # Revoke → should no longer block
            revoke_policy("e2e_lc", "op_alice", reason="test cleanup")
            result = plan_allowed(plan)
            self.assertNotEqual(result, "BLOCK")

    def test_promote_deprecate_gate_flow(self) -> None:
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_lifecycle import deprecate_policy
            from core.policy.policy_gate import plan_allowed

            candidate = {
                "candidate_id": "e2e_dep",
                "pattern_id": "pat_y",
                "suggested_policy": "deny_delete_repo",
                "approval_state": "APPROVED",
                "confidence": 0.9,
                "safety_risk": "low",
            }
            plan = {"run_id": "r_dep", "steps": [{"action": "delete_repo"}]}

            promote(candidate, "op_alice")
            self.assertEqual(plan_allowed(plan), "BLOCK")

            deprecate_policy("e2e_dep", "op_alice")
            self.assertNotEqual(plan_allowed(plan), "BLOCK")

    def test_full_lifecycle_audit_trail(self) -> None:
        """All transitions must appear in the activation log."""
        with _TempRuntime():
            from core.policy.policy_promoter import promote
            from core.policy.policy_lifecycle import revoke_policy
            from core.policy.policy_registry import list_activation_log

            candidate = {
                "candidate_id": "e2e_audit",
                "pattern_id": "pat_z",
                "suggested_policy": "deny_delete_repo",
                "approval_state": "APPROVED",
                "confidence": 0.9,
                "safety_risk": "low",
            }
            promote(candidate, "op_audit")
            revoke_policy("e2e_audit", "op_audit", reason="audit test")

            log = list_activation_log()
            statuses = [e["status"] for e in log]
            self.assertIn("ACTIVATED", statuses)
            self.assertIn("REVOKED", statuses)


if __name__ == "__main__":
    unittest.main()
