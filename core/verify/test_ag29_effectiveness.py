"""AG-29: Policy Effectiveness Verification — test suite.

Suites:
  1. EvaluateDirectPath   — evaluate_policy_effectiveness() direct-path tests
  2. EffectivenessStore   — save/get/list, verification log, atomic writes
  3. RunAndPersist        — run_and_persist() orchestration
  4. VerifierRateLogic    — verify_policy_effectiveness() rate-based analysis
  5. Integration          — user-provided reference tests
"""
from __future__ import annotations

import asyncio
import json
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
        "core.policy.effectiveness_store",
        "core.policy.policy_effectiveness",
        "core.policy.effectiveness_verifier",
    ]:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])


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


def _ts(offset_secs: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_secs))


# ---------------------------------------------------------------------------
# Suite 1 — EvaluateDirectPath
# ---------------------------------------------------------------------------

class TestEvaluateDirectPath(unittest.TestCase):

    def test_keep_when_failures_drop(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p1", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p1")
            self.assertEqual(result["verdict"], "KEEP")

    def test_rollback_when_failures_increase(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p2", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "SUCCESS"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T01:00:00Z", "execution_result": "FAILED"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p2")
            self.assertEqual(result["verdict"], "ROLLBACK_RECOMMENDED")

    def test_review_when_no_change(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p3", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "FAILED"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p3")
            self.assertEqual(result["verdict"], "REVIEW")

    def test_inconclusive_when_not_in_activation_log(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("ghost")
            self.assertEqual(result["verdict"], "INCONCLUSIVE")

    def test_inconclusive_no_post_observations(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p4", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p4")
            self.assertEqual(result["verdict"], "INCONCLUSIVE")

    def test_handles_timestamp_and_ts_activation_fields(self) -> None:
        """Activation log entries using 'timestamp' (not 'ts') must still work."""
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p5", "timestamp": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p5")
            self.assertEqual(result["verdict"], "KEEP")

    def test_handles_outcome_field_alias(self) -> None:
        """Observations using 'outcome'='failure' (not 'execution_result') must work."""
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "p6", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "outcome": "failure"},
                {"timestamp": "2026-03-11T00:00:00Z", "outcome": "success"},
            ])
            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p6")
            self.assertEqual(result["verdict"], "KEEP")


# ---------------------------------------------------------------------------
# Suite 2 — EffectivenessStore
# ---------------------------------------------------------------------------

class TestEffectivenessStore(unittest.TestCase):

    def test_save_and_get(self) -> None:
        with _TempRuntime():
            from core.policy.effectiveness_store import save_effectiveness, get_effectiveness
            save_effectiveness({"policy_id": "s1", "verdict": "KEEP"})
            result = get_effectiveness("s1")
            self.assertIsNotNone(result)
            self.assertEqual(result["verdict"], "KEEP")

    def test_save_is_atomic(self) -> None:
        with _TempRuntime() as root:
            from core.policy.effectiveness_store import save_effectiveness
            save_effectiveness({"policy_id": "s2", "verdict": "REVIEW"})
            tmp_files = list((root / "state").glob("*.tmp"))
            self.assertEqual(tmp_files, [])

    def test_list_effectiveness(self) -> None:
        with _TempRuntime():
            from core.policy.effectiveness_store import save_effectiveness, list_effectiveness
            save_effectiveness({"policy_id": "la", "verdict": "KEEP"})
            save_effectiveness({"policy_id": "lb", "verdict": "REVIEW"})
            all_records = list_effectiveness()
            ids = {r["policy_id"] for r in all_records}
            self.assertIn("la", ids)
            self.assertIn("lb", ids)

    def test_append_verification_log(self) -> None:
        with _TempRuntime():
            from core.policy.effectiveness_store import append_verification_log, list_verification_log
            append_verification_log({"policy_id": "vl1", "verdict": "INCONCLUSIVE"})
            append_verification_log({"policy_id": "vl2", "verdict": "KEEP"})
            log = list_verification_log()
            self.assertEqual(len(log), 2)
            ids = {e["policy_id"] for e in log}
            self.assertIn("vl1", ids)

    def test_get_nonexistent_returns_none(self) -> None:
        with _TempRuntime():
            from core.policy.effectiveness_store import get_effectiveness
            self.assertIsNone(get_effectiveness("no_such_policy"))


# ---------------------------------------------------------------------------
# Suite 3 — RunAndPersist
# ---------------------------------------------------------------------------

class TestRunAndPersist(unittest.TestCase):

    def test_run_and_persist_produces_record(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "rp1", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
            ])
            from core.policy.effectiveness_store import run_and_persist, get_effectiveness, list_verification_log
            record = run_and_persist("rp1")
            self.assertEqual(record["verdict"], "KEEP")
            stored = get_effectiveness("rp1")
            self.assertIsNotNone(stored)
            log = list_verification_log()
            self.assertTrue(any(e.get("policy_id") == "rp1" for e in log))

    def test_run_and_persist_inconclusive_still_persists(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [])
            from core.policy.effectiveness_store import run_and_persist, get_effectiveness
            record = run_and_persist("ghost_policy")
            self.assertEqual(record["verdict"], "INCONCLUSIVE")
            stored = get_effectiveness("ghost_policy")
            self.assertIsNotNone(stored)


# ---------------------------------------------------------------------------
# Suite 4 — VerifierRateLogic
# ---------------------------------------------------------------------------

class TestVerifierRateLogic(unittest.TestCase):

    def test_keep_verdict_with_rate_improvement(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            # 5 before: 4 failures (80%), 5 after: 1 failure (20%) → delta = -0.60 → KEEP
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "r1", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            before = [{"timestamp": f"2026-03-0{i}T00:00:00Z", "execution_result": "FAILED"}
                      for i in range(1, 5)]
            before.append({"timestamp": "2026-03-05T00:00:00Z", "execution_result": "SUCCESS"})
            after = [{"timestamp": f"2026-03-1{i}T00:00:00Z", "execution_result": "SUCCESS"}
                     for i in range(1, 5)]
            after.append({"timestamp": "2026-03-15T00:00:00Z", "execution_result": "FAILED"})
            _write_jsonl(state / "learning_observations.jsonl", before + after)
            from core.policy.effectiveness_verifier import verify_policy_effectiveness
            result = verify_policy_effectiveness("r1")
            self.assertEqual(result["verdict"], "KEEP")

    def test_inconclusive_below_min_observations(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            _write_jsonl(state / "policy_activation_log.jsonl", [
                {"policy_id": "r2", "ts": "2026-03-10T12:00:00Z", "status": "ACTIVATED"},
            ])
            # Only 2 post-promotion observations (MIN_OBSERVATIONS=3)
            _write_jsonl(state / "learning_observations.jsonl", [
                {"timestamp": "2026-03-09T00:00:00Z", "execution_result": "FAILED"},
                {"timestamp": "2026-03-11T00:00:00Z", "execution_result": "SUCCESS"},
                {"timestamp": "2026-03-12T00:00:00Z", "execution_result": "SUCCESS"},
            ])
            from core.policy.effectiveness_verifier import verify_policy_effectiveness
            result = verify_policy_effectiveness("r2")
            self.assertEqual(result["verdict"], "INCONCLUSIVE")


# ---------------------------------------------------------------------------
# Suite 5 — Integration (user-provided reference tests)
# ---------------------------------------------------------------------------

class TestIntegrationUserProvided(unittest.TestCase):
    """Exact tests from user's reference implementation spec."""

    def test_effectiveness_returns_keep_when_failures_drop(self) -> None:
        with _TempRuntime() as root:
            state = _state(root)
            activation_log = [
                {"policy_id": "p1", "timestamp": "2026-03-10T00:00:00Z", "status": "ACTIVATED"}
            ]
            observations = [
                {"timestamp": "2026-03-09T00:00:00Z", "outcome": "failure"},
                {"timestamp": "2026-03-11T00:00:00Z", "outcome": "success"},
            ]
            _write_jsonl(state / "policy_activation_log.jsonl", activation_log)
            _write_jsonl(state / "learning_observations.jsonl", observations)

            from core.policy.policy_effectiveness import evaluate_policy_effectiveness
            result = evaluate_policy_effectiveness("p1")
            self.assertEqual(result["verdict"], "KEEP")


if __name__ == "__main__":
    unittest.main()
