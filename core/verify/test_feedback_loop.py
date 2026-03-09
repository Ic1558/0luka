#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_REPO))

# fail-closed bootstrap for test runner
if not os.environ.get("LUKA_RUNTIME_ROOT"):
    os.environ["ROOT"] = str(ROOT_REPO)
    os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
    os.environ["LUKA_RUNTIME_ROOT"] = tempfile.mkdtemp(prefix="0luka_rt_fl_")


def _reload_fl(runtime_root: Path):
    """Reload feedback_loop with a test LUKA_RUNTIME_ROOT and return the module."""
    os.environ["ROOT"] = str(ROOT_REPO)
    os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    importlib.reload(importlib.import_module("core.config"))
    mod = importlib.reload(importlib.import_module("core.orchestrator.feedback_loop"))
    # Redirect module-level paths to test temp dirs
    mod.FEEDBACK_REGISTRY = runtime_root / "state" / "feedback_registry.jsonl"
    mod.MLS_LESSONS = runtime_root / "mls_lessons.jsonl"
    return mod


class FeedbackLoopTests(unittest.TestCase):
    def test_classify_schema_failure_returns_correct_class(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rt = Path(td).resolve()
            fl = _reload_fl(rt)
            loop = fl.FeedbackLoop()
            result = {
                "status": "rejected",
                "reason": "gate_rejected:clec_schema_validation_failed: 'ts_utc' is a required property",
            }
            self.assertEqual(loop.classify(result), "schema_violation")

    def test_approval_required_is_record_only_not_escalated(self) -> None:
        """QS safety test: approval_required must never escalate."""
        with tempfile.TemporaryDirectory() as td:
            rt = Path(td).resolve()
            fl = _reload_fl(rt)
            loop = fl.FeedbackLoop()

            cls = loop.classify({"status": "approval_required", "reason": ""})
            self.assertEqual(cls, "approval_required")

            # Must not escalate for any job type
            self.assertFalse(loop.should_escalate(cls, job_type=""))
            self.assertFalse(loop.should_escalate(cls, job_type="qs.po_generate"))
            self.assertFalse(loop.should_escalate(cls, job_type="clec.v1"))

    def test_qs_job_type_not_escalated_on_policy_block(self) -> None:
        """QS safety test: policy_block for qs.* must be record_only."""
        with tempfile.TemporaryDirectory() as td:
            rt = Path(td).resolve()
            fl = _reload_fl(rt)
            loop = fl.FeedbackLoop()

            # policy_block for qs.* — must NOT escalate
            self.assertFalse(loop.should_escalate("policy_block", job_type="qs.po_generate"))
            # exec_error for qs.* — MUST escalate
            self.assertTrue(loop.should_escalate("exec_error", job_type="qs.po_generate"))
            # circuit_open for qs.* — MUST escalate
            self.assertTrue(loop.should_escalate("circuit_open", job_type="qs.report_export"))

    def test_record_appends_to_feedback_registry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rt = Path(td).resolve()
            fl = _reload_fl(rt)
            loop = fl.FeedbackLoop()

            loop.record("task_001", "trace_001", "exec_error", "escalate", "failed")
            registry = fl.FEEDBACK_REGISTRY
            self.assertTrue(registry.exists())
            rows = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(rows)
            last = rows[-1]
            self.assertEqual(last["error_class"], "exec_error")
            self.assertEqual(last["trace_id"], "trace_001")
            self.assertEqual(last["action"], "escalate")

    def test_run_cycle_escalates_to_remediation_engine_on_exec_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rt = Path(td).resolve()
            fl = _reload_fl(rt)

            # Plant dispatch_latest.json with exec_error (non-QS job so escalation fires)
            dispatch = rt / "artifacts" / "dispatch_latest.json"
            dispatch.parent.mkdir(parents=True, exist_ok=True)
            dispatch.write_text(
                json.dumps({
                    "task_id": "t_exec_001",
                    "status": "failed",
                    "job_type": "clec.v1",
                    "reason": "exec_error",
                }),
                encoding="utf-8",
            )
            fl.DISPATCH_LATEST = dispatch

            result = fl.FeedbackLoop().run_cycle()

            self.assertEqual(result["cycle"], "complete")
            self.assertEqual(result["error_class"], "exec_error")
            self.assertTrue(result["escalated"])

            # Registry must have an escalate entry
            rows = [
                json.loads(ln)
                for ln in fl.FEEDBACK_REGISTRY.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            self.assertTrue(any(r["action"] == "escalate" for r in rows))


def main() -> int:
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
