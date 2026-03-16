"""AG-33: Drift Repair Planning Engine — test suite.

Suites:
  1. DriftTypeClassification  — classify_drift_type() covers all 10 drift classes
  2. RepairPlanGeneration     — generate_repair_plan() produces required fields
  3. EscalatedFindingReader   — list_escalated_findings() filters correctly
  4. PlanStorage              — store_repair_plan() appends only, run_repair_planning() E2E
  5. APIEndpoints             — GET/POST route handlers
  6. SafetyInvariants         — planner never mutates findings, codebase, or baseline
  7. SmokeRepairPlanning      — live smoke run against current runtime
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


def _write_status(rt: Path, statuses: dict[str, str], operator: str = "boss") -> None:
    """Write a drift_finding_status.json with given finding_id → status."""
    import time
    status_map = {
        fid: {
            "finding_id": fid,
            "status": status,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "operator_id": operator,
            "note": "",
        }
        for fid, status in statuses.items()
    }
    (rt / "state" / "drift_finding_status.json").write_text(
        json.dumps(status_map), encoding="utf-8"
    )


def _write_findings_jsonl(rt: Path, findings: list[dict[str, Any]]) -> None:
    """Write drift_findings.jsonl for enrichment."""
    path = rt / "state" / "drift_findings.jsonl"
    path.write_text(
        "\n".join(json.dumps(f) for f in findings) + "\n",
        encoding="utf-8",
    )


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json() -> dict[str, Any]:
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite 1 — DriftTypeClassification
# ---------------------------------------------------------------------------

class TestDriftTypeClassification(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.drift_repair_planner import classify_drift_type
        self.classify = classify_drift_type

    def _finding(self, drift_class: str, **kw: Any) -> dict[str, Any]:
        return {"drift_class": drift_class, "component": "some.module", "evidence": "test", **kw}

    def test_classify_missing_component(self) -> None:
        r = self.classify(self._finding("expected_by_SOT_but_missing"))
        self.assertEqual(r["drift_type"], "missing_component")
        self.assertEqual(r["repair_strategy"], "create_missing_component")

    def test_classify_wiring_gap(self) -> None:
        r = self.classify(self._finding("exists_but_not_wired"))
        self.assertEqual(r["drift_type"], "wiring_gap")
        self.assertEqual(r["repair_strategy"], "wire_component_into_runtime_path")

    def test_classify_active_not_canonical(self) -> None:
        r = self.classify(self._finding("active_but_not_canonical"))
        self.assertEqual(r["drift_type"], "wiring_gap")

    def test_classify_api_surface_drift(self) -> None:
        r = self.classify(self._finding("API_exposed_but_not_in_diagram"))
        self.assertEqual(r["drift_type"], "api_surface_drift")
        self.assertEqual(r["repair_strategy"], "align_api_surface")

    def test_classify_operator_gate_regression(self) -> None:
        r = self.classify(self._finding("operator_gate_missing"))
        self.assertEqual(r["drift_type"], "operator_gate_regression")
        self.assertEqual(r["repair_strategy"], "restore_operator_guard")

    def test_classify_runtime_state_missing(self) -> None:
        r = self.classify(self._finding("state_file_expected_but_not_produced"))
        self.assertEqual(r["drift_type"], "runtime_state_missing")

    def test_classify_naming_drift(self) -> None:
        r = self.classify(self._finding("naming_drift_only"))
        self.assertEqual(r["drift_type"], "naming_drift")
        self.assertEqual(r["repair_strategy"], "rename_or_document_alias")

    def test_classify_diagram_mismatch(self) -> None:
        r = self.classify(self._finding("diagram_path_mismatch"))
        self.assertEqual(r["drift_type"], "diagram_mismatch")

    def test_classify_legacy_overlap(self) -> None:
        r = self.classify(self._finding("legacy_component_still_active"))
        self.assertEqual(r["drift_type"], "legacy_path_overlap")

    def test_classify_unknown_falls_back_gracefully(self) -> None:
        r = self.classify(self._finding("unknown"))
        self.assertIn(r["drift_type"], ("documentation_drift", "unknown"))
        self.assertGreater(r["confidence"], 0.0)

    def test_classify_returns_confidence(self) -> None:
        r = self.classify(self._finding("operator_gate_missing"))
        self.assertGreaterEqual(r["confidence"], 0.0)
        self.assertLessEqual(r["confidence"], 1.0)

    def test_all_mandatory_drift_classes_classifiable(self) -> None:
        mandatory = [
            "expected_by_SOT_but_missing", "exists_but_not_wired",
            "active_but_not_canonical", "API_exposed_but_not_in_diagram",
            "canonical_component_but_no_runtime_evidence", "operator_gate_missing",
            "state_file_expected_but_not_produced", "naming_drift_only",
            "diagram_path_mismatch", "legacy_component_still_active",
        ]
        for dc in mandatory:
            r = self.classify(self._finding(dc))
            self.assertIn("drift_type", r, f"Missing drift_type for {dc}")
            self.assertIn("repair_strategy", r, f"Missing repair_strategy for {dc}")

    def test_evidence_text_refines_unknown_class(self) -> None:
        """Finding with 'unknown' drift_class but gate-related evidence → operator_gate."""
        r = self.classify({
            "drift_class": "unknown",
            "component": "POST /api/foo",
            "evidence": "no operator_id check, no 403",
        })
        self.assertEqual(r["drift_type"], "operator_gate_regression")


# ---------------------------------------------------------------------------
# Suite 2 — RepairPlanGeneration
# ---------------------------------------------------------------------------

class TestRepairPlanGeneration(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.drift_repair_planner import generate_repair_plan
        self.generate = generate_repair_plan

    def _finding(self, **kw: Any) -> dict[str, Any]:
        return {
            "finding_id": "f-test",
            "drift_class": "exists_but_not_wired",
            "component": "core.orchestrator.feedback_loop",
            "evidence": "not imported in task_dispatcher",
            "severity": "MEDIUM",
            **kw,
        }

    def test_plan_has_all_required_fields(self) -> None:
        plan = self.generate(self._finding())
        required = [
            "ts", "plan_id", "finding_id", "severity", "drift_class",
            "drift_type", "repair_strategy", "target_files",
            "proposed_actions", "operator_action_required", "status", "confidence",
        ]
        for field in required:
            self.assertIn(field, plan, f"Plan missing field '{field}'")

    def test_operator_action_required_is_always_true(self) -> None:
        plan = self.generate(self._finding())
        self.assertTrue(plan["operator_action_required"])

    def test_status_starts_as_proposed(self) -> None:
        plan = self.generate(self._finding())
        self.assertEqual(plan["status"], "PROPOSED")

    def test_proposed_actions_is_nonempty_list(self) -> None:
        plan = self.generate(self._finding())
        self.assertIsInstance(plan["proposed_actions"], list)
        self.assertGreater(len(plan["proposed_actions"]), 0)

    def test_confidence_is_float_between_0_and_1(self) -> None:
        plan = self.generate(self._finding())
        self.assertIsInstance(plan["confidence"], float)
        self.assertGreaterEqual(plan["confidence"], 0.0)
        self.assertLessEqual(plan["confidence"], 1.0)

    def test_target_files_is_list(self) -> None:
        plan = self.generate(self._finding())
        self.assertIsInstance(plan["target_files"], list)

    def test_finding_id_preserved(self) -> None:
        plan = self.generate(self._finding(finding_id="unique-123"))
        self.assertEqual(plan["finding_id"], "unique-123")

    def test_plan_id_is_unique(self) -> None:
        p1 = self.generate(self._finding())
        p2 = self.generate(self._finding())
        self.assertNotEqual(p1["plan_id"], p2["plan_id"])

    def test_operator_gate_finding_generates_restore_guard_strategy(self) -> None:
        plan = self.generate(self._finding(drift_class="operator_gate_missing"))
        self.assertEqual(plan["repair_strategy"], "restore_operator_guard")

    def test_route_component_infers_mcs_target_file(self) -> None:
        plan = self.generate(self._finding(
            drift_class="API_exposed_but_not_in_diagram",
            component="POST /api/something",
        ))
        target_names = [t.lower() for t in plan["target_files"]]
        self.assertTrue(
            any("mission_control" in t for t in target_names),
            f"Expected MCS in target_files, got: {plan['target_files']}"
        )


# ---------------------------------------------------------------------------
# Suite 3 — EscalatedFindingReader
# ---------------------------------------------------------------------------

class TestEscalatedFindingReader(unittest.TestCase):

    def test_returns_only_escalated(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {
                "f-001": "ESCALATED",
                "f-002": "ACCEPTED",
                "f-003": "OPEN",
                "f-004": "ESCALATED",
            })
            from core.audit.drift_repair_planner import list_escalated_findings
            results = list_escalated_findings()
            fids = {r["finding_id"] for r in results}
            self.assertEqual(fids, {"f-001", "f-004"})

    def test_returns_empty_when_no_escalated(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-001": "ACCEPTED", "f-002": "OPEN"})
            from core.audit.drift_repair_planner import list_escalated_findings
            self.assertEqual(list_escalated_findings(), [])

    def test_returns_empty_when_no_status_file(self) -> None:
        with _TempRuntime():
            from core.audit.drift_repair_planner import list_escalated_findings
            self.assertEqual(list_escalated_findings(), [])

    def test_enriches_from_drift_findings_jsonl(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-005": "ESCALATED"})
            _write_findings_jsonl(rt, [{
                "id": "f-005",
                "drift_class": "operator_gate_missing",
                "component": "POST /api/foo",
                "evidence": "no 403",
                "severity": "CRITICAL",
            }])
            from core.audit.drift_repair_planner import list_escalated_findings
            results = list_escalated_findings()
            self.assertEqual(len(results), 1)
            # Enriched with drift_class from findings
            self.assertEqual(results[0].get("drift_class"), "operator_gate_missing")

    def test_works_without_drift_findings_jsonl(self) -> None:
        """Should still return ESCALATED findings even without enrichment data."""
        with _TempRuntime() as rt:
            _write_status(rt, {"f-006": "ESCALATED"})
            # No drift_findings.jsonl created
            from core.audit.drift_repair_planner import list_escalated_findings
            results = list_escalated_findings()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["finding_id"], "f-006")


# ---------------------------------------------------------------------------
# Suite 4 — PlanStorage
# ---------------------------------------------------------------------------

class TestPlanStorage(unittest.TestCase):

    def test_store_repair_plan_appends_jsonl(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_repair_planner import store_repair_plan
            store_repair_plan({"finding_id": "f-1", "plan_id": "p1", "status": "PROPOSED"})
            store_repair_plan({"finding_id": "f-2", "plan_id": "p2", "status": "PROPOSED"})
            plans_path = rt / "state" / "drift_repair_plans.jsonl"
            self.assertTrue(plans_path.exists())
            lines = plans_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)

    def test_each_stored_line_is_valid_json(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.drift_repair_planner import store_repair_plan, generate_repair_plan
            plan = generate_repair_plan({
                "finding_id": "f-store", "drift_class": "exists_but_not_wired",
                "component": "core.some.module", "evidence": "e", "severity": "MEDIUM",
            })
            store_repair_plan(plan)
            lines = (rt / "state" / "drift_repair_plans.jsonl").read_text().strip().splitlines()
            for i, line in enumerate(lines):
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    self.fail(f"Line {i} invalid JSON: {exc}")

    def test_run_repair_planning_generates_plans_for_escalated(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-run-1": "ESCALATED", "f-run-2": "ESCALATED"})
            _write_findings_jsonl(rt, [
                {"id": "f-run-1", "drift_class": "exists_but_not_wired", "component": "core.x", "evidence": "e", "severity": "MEDIUM"},
                {"id": "f-run-2", "drift_class": "operator_gate_missing", "component": "POST /api/y", "evidence": "no 403", "severity": "CRITICAL"},
            ])
            from core.audit.drift_repair_planner import run_repair_planning
            summary = run_repair_planning()
            self.assertEqual(summary["escalated_found"], 2)
            self.assertEqual(summary["plans_generated"], 2)

    def test_run_repair_planning_produces_latest_summary(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-latest": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()
            latest_path = rt / "state" / "drift_repair_plan_latest.json"
            self.assertTrue(latest_path.exists())
            data = json.loads(latest_path.read_text())
            self.assertIn("plans_generated", data)

    def test_run_repair_planning_no_escalated_returns_zero(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-open": "OPEN", "f-acc": "ACCEPTED"})
            from core.audit.drift_repair_planner import run_repair_planning
            summary = run_repair_planning()
            self.assertEqual(summary["escalated_found"], 0)
            self.assertEqual(summary["plans_generated"], 0)

    def test_list_all_plans_returns_stored_plans(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-list": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning, list_all_plans
            run_repair_planning()
            plans = list_all_plans()
            self.assertGreaterEqual(len(plans), 1)

    def test_get_plans_for_finding_filters_correctly(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"fA": "ESCALATED", "fB": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning, get_plans_for_finding
            run_repair_planning()
            plans_a = get_plans_for_finding("fA")
            for p in plans_a:
                self.assertEqual(p["finding_id"], "fA")


# ---------------------------------------------------------------------------
# Suite 5 — APIEndpoints
# ---------------------------------------------------------------------------

class TestAPIEndpoints(unittest.TestCase):

    def test_drift_repair_run_requires_operator_id(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_repair import drift_repair_run_endpoint
            req = _mock_request({})   # no operator_id
            resp = asyncio.run(drift_repair_run_endpoint(req))
            self.assertEqual(resp.status_code, 403)

    def test_drift_repair_run_with_operator_returns_200(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {})   # no escalated findings
            from interface.operator.api_drift_repair import drift_repair_run_endpoint
            req = _mock_request({"operator_id": "boss"})
            resp = asyncio.run(drift_repair_run_endpoint(req))
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.body)
            self.assertTrue(body["ok"])

    def test_drift_repair_plans_list_returns_json(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_repair import drift_repair_plans_list
            result = asyncio.run(drift_repair_plans_list())
            self.assertIn("ok", result)
            self.assertIn("plans", result)
            self.assertIsInstance(result["plans"], list)

    def test_drift_repair_plan_by_finding_returns_json(self) -> None:
        with _TempRuntime():
            from interface.operator.api_drift_repair import drift_repair_plan_by_finding
            result = asyncio.run(drift_repair_plan_by_finding("f-unknown"))
            self.assertIn("ok", result)
            self.assertIn("plans", result)
            self.assertEqual(result["plans"], [])

    def test_drift_repair_run_returns_plans_in_response(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-api": "ESCALATED"})
            _write_findings_jsonl(rt, [{
                "id": "f-api", "drift_class": "exists_but_not_wired",
                "component": "core.x.y", "evidence": "e", "severity": "MEDIUM",
            }])
            from interface.operator.api_drift_repair import drift_repair_run_endpoint
            req = _mock_request({"operator_id": "boss"})
            resp = asyncio.run(drift_repair_run_endpoint(req))
            body = json.loads(resp.body)
            self.assertEqual(body["plans_generated"], 1)
            self.assertEqual(len(body["plans"]), 1)


# ---------------------------------------------------------------------------
# Suite 6 — SafetyInvariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants(unittest.TestCase):

    def test_planner_does_not_modify_drift_finding_status(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-safe": "ESCALATED"})
            status_path = rt / "state" / "drift_finding_status.json"
            original = status_path.read_text()

            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()

            self.assertEqual(status_path.read_text(), original,
                             "run_repair_planning() modified drift_finding_status.json — invariant violated")

    def test_planner_does_not_modify_drift_governance_log(self) -> None:
        with _TempRuntime() as rt:
            log_path = rt / "state" / "drift_governance_log.jsonl"
            log_path.write_text('{"sentinel":"must_not_change"}\n')

            _write_status(rt, {"f-safe2": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()

            self.assertEqual(log_path.read_text(), '{"sentinel":"must_not_change"}\n')

    def test_planner_does_not_modify_audit_baseline(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-safe3": "ESCALATED"})
            import core.audit.audit_baseline as bmod
            baseline_path = Path(bmod.__file__)
            mtime_before = baseline_path.stat().st_mtime

            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()

            self.assertEqual(baseline_path.stat().st_mtime, mtime_before,
                             "Planner modified audit_baseline.py — invariant violated")

    def test_planner_own_outputs_are_limited(self) -> None:
        with _TempRuntime() as rt:
            state_d = rt / "state"
            before = set(p.name for p in state_d.iterdir())
            _write_status(rt, {"f-out": "ESCALATED"})
            after_status = set(p.name for p in state_d.iterdir())

            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()

            after = set(p.name for p in state_d.iterdir())
            new_files = after - after_status
            allowed = {"drift_repair_plans.jsonl", "drift_repair_plan_latest.json"}
            unexpected = new_files - allowed
            self.assertEqual(unexpected, set(),
                             f"Planner created unexpected files: {unexpected}")

    def test_plans_have_operator_action_required_true(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-op": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning, list_all_plans
            run_repair_planning()
            for plan in list_all_plans():
                self.assertTrue(plan.get("operator_action_required"),
                                f"Plan {plan.get('plan_id')} missing operator_action_required=True")

    def test_plans_start_as_proposed(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"f-status": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning, list_all_plans
            run_repair_planning()
            for plan in list_all_plans():
                self.assertEqual(plan.get("status"), "PROPOSED",
                                 f"Plan {plan.get('plan_id')} status is not PROPOSED")


# ---------------------------------------------------------------------------
# Suite 7 — SmokeRepairPlanning
# ---------------------------------------------------------------------------

class TestSmokeRepairPlanning(unittest.TestCase):

    def test_smoke_run_repair_planning_without_escalated_returns_zero(self) -> None:
        """On clean main with no ESCALATED findings, planning returns 0 plans."""
        with _TempRuntime():
            from core.audit.drift_repair_planner import run_repair_planning
            summary = run_repair_planning()
            self.assertIsInstance(summary, dict)
            self.assertIn("plans_generated", summary)
            # No escalated findings on clean runtime
            self.assertEqual(summary["plans_generated"], 0)

    def test_smoke_escalate_then_plan(self) -> None:
        """Escalate a finding via AG-32, then run AG-33 to generate a plan."""
        with _TempRuntime() as rt:
            # Simulate AG-32 escalation
            from core.audit.drift_governance import escalate_finding
            escalate_finding("smoke-f1", operator_id="boss", note="smoke test finding")

            # Write enrichment data as if AG-31 produced it
            _write_findings_jsonl(rt, [{
                "id": "smoke-f1",
                "drift_class": "exists_but_not_wired",
                "component": "core.orchestrator.feedback_loop",
                "evidence": "not imported in task_dispatcher",
                "severity": "MEDIUM",
            }])

            # Run AG-33
            from core.audit.drift_repair_planner import run_repair_planning
            summary = run_repair_planning()

            self.assertEqual(summary["escalated_found"], 1)
            self.assertEqual(summary["plans_generated"], 1)

            plan = summary["plans"][0]
            self.assertEqual(plan["finding_id"], "smoke-f1")
            self.assertEqual(plan["drift_type"], "wiring_gap")
            self.assertEqual(plan["repair_strategy"], "wire_component_into_runtime_path")
            self.assertTrue(plan["operator_action_required"])
            self.assertEqual(plan["status"], "PROPOSED")

    def test_smoke_plans_jsonl_is_appendable(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"smoke-f2": "ESCALATED", "smoke-f3": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()
            run_repair_planning()  # run twice
            plans_path = rt / "state" / "drift_repair_plans.jsonl"
            lines = plans_path.read_text().strip().splitlines()
            # Should have 4 lines (2 findings × 2 runs)
            self.assertEqual(len(lines), 4)

    def test_smoke_api_get_plans_returns_stored(self) -> None:
        with _TempRuntime() as rt:
            _write_status(rt, {"smoke-api": "ESCALATED"})
            from core.audit.drift_repair_planner import run_repair_planning
            run_repair_planning()
            from interface.operator.api_drift_repair import drift_repair_plans_list
            result = asyncio.run(drift_repair_plans_list())
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["total"], 1)


if __name__ == "__main__":
    unittest.main()
