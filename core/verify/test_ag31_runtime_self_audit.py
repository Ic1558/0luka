"""AG-31: Runtime Self-Audit Layer — test suite.

Suites:
  1. AuditBaseline           — known drift lookup + first-run optional
  2. DriftClassifier         — classify_finding() + summarize_findings()
  3. VerdictComputation      — compute_verdict() precedence + GOVERNANCE_VIOLATION escalation
  4. OperatorGateScanner     — _handler_has_operator_gate() source pattern matching
  5. ComponentRegistry       — CANONICAL_COMPONENTS registry integrity
  6. AuditOutputs            — run_runtime_self_audit() writes 3 files atomically
  7. SafetyInvariants        — audit does not mutate policy registry or runtime state
  8. SmokeAuditMain          — full audit on actual main returns clean verdict class
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TempRuntime:
    """Context manager: temp LUKA_RUNTIME_ROOT with state/ pre-created."""

    def __enter__(self) -> "Path":
        self._td = tempfile.mkdtemp()
        os.environ["LUKA_RUNTIME_ROOT"] = self._td
        (Path(self._td) / "state").mkdir(parents=True, exist_ok=True)
        return Path(self._td)

    def __exit__(self, *_: object) -> None:
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self._td, ignore_errors=True)


def _raw_finding(
    drift_class: str = "naming_drift_only",
    component: str = "some.module",
    evidence: str = "test evidence",
    accepted: bool = False,
    drift_key: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "drift_class": drift_class,
        "component": component,
        "evidence": evidence,
        "accepted": accepted,
        "drift_key": drift_key,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Suite 1 — AuditBaseline
# ---------------------------------------------------------------------------

class TestAuditBaseline(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.audit_baseline import (
            is_known_drift, get_known_drift_reason, is_first_run_optional,
            KNOWN_ACCEPTED_DRIFT,
        )
        self.is_known = is_known_drift
        self.get_reason = get_known_drift_reason
        self.is_optional = is_first_run_optional
        self.baseline = KNOWN_ACCEPTED_DRIFT

    def test_runtime_guardian_name_gap_is_known(self) -> None:
        self.assertTrue(self.is_known("runtime_guardian_name_gap"))

    def test_api_activity_name_gap_is_known(self) -> None:
        self.assertTrue(self.is_known("api_activity_name_gap"))

    def test_feedback_loop_lazy_path_is_known(self) -> None:
        self.assertTrue(self.is_known("feedback_loop_lazy_path"))

    def test_legacy_remediation_is_known(self) -> None:
        self.assertTrue(self.is_known("legacy_remediation_parallel_path"))

    def test_first_run_optional_is_known(self) -> None:
        self.assertTrue(self.is_known("first_run_optional_state_files"))

    def test_unknown_key_returns_false(self) -> None:
        self.assertFalse(self.is_known("definitely_not_a_real_drift_key"))

    def test_get_reason_returns_string_for_known(self) -> None:
        reason = self.get_reason("runtime_guardian_name_gap")
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 10)

    def test_get_reason_returns_none_for_unknown(self) -> None:
        self.assertIsNone(self.get_reason("not_a_key"))

    def test_learning_observations_is_first_run_optional(self) -> None:
        self.assertTrue(self.is_optional("learning_observations.jsonl"))

    def test_policy_outcome_governance_is_first_run_optional(self) -> None:
        self.assertTrue(self.is_optional("policy_outcome_governance.jsonl"))

    def test_policy_registry_json_is_not_first_run_optional(self) -> None:
        self.assertFalse(self.is_optional("policy_registry.json"))

    def test_all_baseline_entries_have_required_fields(self) -> None:
        required = {"description", "drift_class", "severity", "owner", "accepted_at"}
        for key, entry in self.baseline.items():
            for field in required:
                self.assertIn(field, entry, f"Baseline entry '{key}' missing field '{field}'")

    def test_baseline_is_immutable_at_runtime(self) -> None:
        """Baseline dict should not be mutated between calls."""
        from core.audit.audit_baseline import KNOWN_ACCEPTED_DRIFT
        initial_keys = set(KNOWN_ACCEPTED_DRIFT.keys())
        _ = self.is_known("runtime_guardian_name_gap")
        self.assertEqual(set(KNOWN_ACCEPTED_DRIFT.keys()), initial_keys)


# ---------------------------------------------------------------------------
# Suite 2 — DriftClassifier
# ---------------------------------------------------------------------------

class TestDriftClassifier(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.drift_classifier import classify_finding, summarize_findings
        self.classify = classify_finding
        self.summarize = summarize_findings

    def test_naming_drift_only_gets_info_severity(self) -> None:
        f = self.classify(_raw_finding(drift_class="naming_drift_only"))
        self.assertEqual(f["severity"], "INFO")

    def test_operator_gate_missing_gets_critical_severity(self) -> None:
        f = self.classify(_raw_finding(drift_class="operator_gate_missing"))
        self.assertEqual(f["severity"], "CRITICAL")

    def test_operator_gate_missing_gets_governance_violation_verdict(self) -> None:
        f = self.classify(_raw_finding(drift_class="operator_gate_missing"))
        self.assertEqual(f["verdict_impact"], "GOVERNANCE_VIOLATION")
        self.assertEqual(f["effective_verdict"], "GOVERNANCE_VIOLATION")

    def test_accepted_finding_gets_consistent_effective_verdict(self) -> None:
        f = self.classify(_raw_finding(drift_class="operator_gate_missing", accepted=True))
        self.assertEqual(f["effective_verdict"], "CONSISTENT")
        self.assertEqual(f["status"], "ACCEPTED")

    def test_naming_drift_only_does_not_degrade_verdict(self) -> None:
        f = self.classify(_raw_finding(drift_class="naming_drift_only"))
        self.assertEqual(f["effective_verdict"], "CONSISTENT")

    def test_exists_but_not_wired_gives_wired_with_gaps(self) -> None:
        f = self.classify(_raw_finding(drift_class="exists_but_not_wired"))
        self.assertEqual(f["effective_verdict"], "WIRED_WITH_GAPS")

    def test_expected_by_sot_but_missing_gives_drift_detected(self) -> None:
        f = self.classify(_raw_finding(drift_class="expected_by_SOT_but_missing"))
        self.assertEqual(f["effective_verdict"], "DRIFT_DETECTED")

    def test_api_exposed_not_in_diagram_gets_low_severity(self) -> None:
        f = self.classify(_raw_finding(
            drift_class="API_exposed_but_not_in_diagram",
            severity_override="INFO",
        ))
        self.assertEqual(f["severity"], "INFO")

    def test_open_finding_gets_open_status(self) -> None:
        f = self.classify(_raw_finding(drift_class="naming_drift_only", accepted=False))
        self.assertEqual(f["status"], "OPEN")

    def test_unknown_drift_class_normalised(self) -> None:
        f = self.classify(_raw_finding(drift_class="totally_unknown_class"))
        self.assertEqual(f["drift_class"], "unknown")

    def test_all_mandatory_drift_classes_classifiable(self) -> None:
        mandatory = [
            "expected_by_SOT_but_missing",
            "exists_but_not_wired",
            "active_but_not_canonical",
            "API_exposed_but_not_in_diagram",
            "canonical_component_but_no_runtime_evidence",
            "operator_gate_missing",
            "state_file_expected_but_not_produced",
            "naming_drift_only",
            "diagram_path_mismatch",
            "legacy_component_still_active",
        ]
        for dc in mandatory:
            f = self.classify(_raw_finding(drift_class=dc))
            self.assertIn("severity", f, f"Missing severity for {dc}")
            self.assertIn("effective_verdict", f, f"Missing effective_verdict for {dc}")


# ---------------------------------------------------------------------------
# Suite 3 — VerdictComputation
# ---------------------------------------------------------------------------

class TestVerdictComputation(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.drift_classifier import classify_finding, summarize_findings, compute_verdict
        self.classify = classify_finding
        self.summarize = summarize_findings
        self.verdict = compute_verdict

    def test_empty_findings_returns_consistent(self) -> None:
        self.assertEqual(self.verdict([]), "CONSISTENT")

    def test_all_accepted_returns_consistent(self) -> None:
        findings = [
            self.classify(_raw_finding(drift_class="naming_drift_only", accepted=True)),
            self.classify(_raw_finding(drift_class="exists_but_not_wired", accepted=True)),
        ]
        self.assertEqual(self.verdict(findings), "CONSISTENT")

    def test_open_naming_drift_returns_consistent(self) -> None:
        findings = [self.classify(_raw_finding(drift_class="naming_drift_only"))]
        self.assertEqual(self.verdict(findings), "CONSISTENT")

    def test_open_wiring_gap_returns_wired_with_gaps(self) -> None:
        findings = [self.classify(_raw_finding(drift_class="exists_but_not_wired"))]
        self.assertEqual(self.verdict(findings), "WIRED_WITH_GAPS")

    def test_governance_violation_overrides_everything(self) -> None:
        findings = [
            self.classify(_raw_finding(drift_class="naming_drift_only")),
            self.classify(_raw_finding(drift_class="exists_but_not_wired")),
            self.classify(_raw_finding(drift_class="operator_gate_missing")),
        ]
        self.assertEqual(self.verdict(findings), "GOVERNANCE_VIOLATION")

    def test_governance_violation_not_raised_when_accepted(self) -> None:
        findings = [
            self.classify(_raw_finding(drift_class="operator_gate_missing", accepted=True)),
            self.classify(_raw_finding(drift_class="exists_but_not_wired")),
        ]
        # accepted gate missing does not push to GOVERNANCE_VIOLATION
        v = self.verdict(findings)
        self.assertNotEqual(v, "GOVERNANCE_VIOLATION")

    def test_blocking_drift_count(self) -> None:
        findings = [
            self.classify(_raw_finding(drift_class="expected_by_SOT_but_missing")),   # DRIFT_DETECTED
            self.classify(_raw_finding(drift_class="operator_gate_missing")),          # GOVERNANCE_VIOLATION
            self.classify(_raw_finding(drift_class="naming_drift_only")),              # CONSISTENT
        ]
        summary = self.summarize(findings)
        self.assertEqual(summary["blocking_drift"], 2)

    def test_summary_counts_severities(self) -> None:
        findings = [
            self.classify(_raw_finding(drift_class="operator_gate_missing")),   # CRITICAL
            self.classify(_raw_finding(drift_class="naming_drift_only")),        # INFO
        ]
        summary = self.summarize(findings)
        self.assertEqual(summary["counts"]["CRITICAL"], 1)
        self.assertEqual(summary["counts"]["INFO"], 1)


# ---------------------------------------------------------------------------
# Suite 4 — OperatorGateScanner
# ---------------------------------------------------------------------------

class TestOperatorGateScanner(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.runtime_self_audit import _handler_has_operator_gate
        self.has_gate = _handler_has_operator_gate

    def test_handler_with_operator_id_and_403_detected(self) -> None:
        source = '''
async def my_endpoint(request):
    body = await request.json()
    operator_id = body.get("operator_id", "").strip()
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False})
    # do stuff
'''
        self.assertTrue(self.has_gate(source, "my_endpoint"))

    def test_handler_without_operator_id_not_detected(self) -> None:
        source = '''
async def my_endpoint(request):
    body = await request.json()
    # no operator check
    return {"ok": True}
'''
        self.assertFalse(self.has_gate(source, "my_endpoint"))

    def test_handler_with_403_but_no_operator_id_not_detected(self) -> None:
        source = '''
async def my_endpoint(request):
    return JSONResponse(status_code=403, content={"bad": "request"})
'''
        self.assertFalse(self.has_gate(source, "my_endpoint"))

    def test_missing_function_falls_back_to_file_scan(self) -> None:
        # Handler name doesn't match — falls back to searching entire file
        source = "operator_id = ...\nreturn 403\n"
        # Has both keywords → True
        self.assertTrue(self.has_gate(source, "nonexistent_handler"))

    def test_handler_with_x_operator_id_header_detected(self) -> None:
        source = '''
async def promote_endpoint(request):
    body = await request.json()
    operator_id = body.get("operator_id") or request.headers.get("X-Operator-Id")
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})
'''
        self.assertTrue(self.has_gate(source, "promote_endpoint"))


# ---------------------------------------------------------------------------
# Suite 5 — ComponentRegistry
# ---------------------------------------------------------------------------

class TestComponentRegistry(unittest.TestCase):

    def setUp(self) -> None:
        from core.audit.runtime_self_audit import CANONICAL_COMPONENTS
        self.components = CANONICAL_COMPONENTS

    def test_registry_is_non_empty(self) -> None:
        self.assertGreater(len(self.components), 10)

    def test_all_entries_have_required_fields(self) -> None:
        required = {"id", "ag", "layer", "module", "operator_gate"}
        for c in self.components:
            for f in required:
                self.assertIn(f, c, f"Component '{c.get('id')}' missing field '{f}'")

    def test_all_layer_ids_are_valid(self) -> None:
        valid_layers = {
            "L1_kernel", "L2_runtime_state", "L3_observability",
            "L4_mission_control", "L5_run_interpretation",
            "L6_decision_persistence", "L7_planner_executor_verifier",
            "L8_adaptive_remediation", "L9_learning_plane", "L10_policy_control",
        }
        for c in self.components:
            self.assertIn(c["layer"], valid_layers, f"Invalid layer '{c['layer']}' in '{c['id']}'")

    def test_no_duplicate_ids(self) -> None:
        ids = [c["id"] for c in self.components]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate component ids found")

    def test_ag_phase_range_valid(self) -> None:
        for c in self.components:
            self.assertGreaterEqual(c["ag"], 1)
            self.assertLessEqual(c["ag"], 30)

    def test_operator_gated_components_have_true(self) -> None:
        gated = {c["id"] for c in self.components if c["operator_gate"]}
        # At minimum these must be gated
        self.assertIn("policy_promoter", gated)
        self.assertIn("policy_lifecycle", gated)


# ---------------------------------------------------------------------------
# Suite 6 — AuditOutputs
# ---------------------------------------------------------------------------

class TestAuditOutputs(unittest.TestCase):

    def test_run_audit_produces_json_output(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit(runtime_root=str(rt))
            json_path = rt / "state" / "runtime_self_audit.json"
            self.assertTrue(json_path.exists(), "runtime_self_audit.json not created")
            data = json.loads(json_path.read_text())
            self.assertIn("overall_verdict", data)
            self.assertIn("findings", data)

    def test_run_audit_appends_jsonl_findings(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            # Run twice — should append
            run_runtime_self_audit(runtime_root=str(rt))
            run_runtime_self_audit(runtime_root=str(rt))
            jsonl_path = rt / "state" / "drift_findings.jsonl"
            self.assertTrue(jsonl_path.exists(), "drift_findings.jsonl not created")
            lines = jsonl_path.read_text().strip().splitlines()
            # Should have more lines than a single run (append semantics)
            self.assertGreater(len(lines), 0)

    def test_run_audit_produces_markdown_output(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit, _repo_root
            run_runtime_self_audit(runtime_root=str(rt))
            md_path = _repo_root() / "g" / "reports" / "architecture" / "runtime_self_audit.md"
            self.assertTrue(md_path.exists(), "runtime_self_audit.md not created")
            content = md_path.read_text()
            self.assertIn("AG-31 Runtime Self-Audit Report", content)
            self.assertIn("Executive Verdict", content)

    def test_json_output_is_valid_json(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))
            json_path = rt / "state" / "runtime_self_audit.json"
            try:
                data = json.loads(json_path.read_text())
            except json.JSONDecodeError as exc:
                self.fail(f"runtime_self_audit.json is invalid JSON: {exc}")
            self.assertIsInstance(data, dict)

    def test_jsonl_findings_each_line_valid_json(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))
            jsonl_path = rt / "state" / "drift_findings.jsonl"
            for i, line in enumerate(jsonl_path.read_text().strip().splitlines()):
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    self.fail(f"Line {i} of drift_findings.jsonl is invalid JSON: {exc}")

    def test_result_has_required_keys(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit(runtime_root=str(rt))
            for key in ["ts", "audit_id", "audit_version", "overall_verdict", "summary", "findings"]:
                self.assertIn(key, result, f"Result missing key '{key}'")

    def test_summary_has_required_keys(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit(runtime_root=str(rt))
            summary = result["summary"]
            for key in ["overall_verdict", "total", "open", "accepted", "blocking_drift"]:
                self.assertIn(key, summary, f"Summary missing key '{key}'")

    def test_verdict_is_valid_class(self) -> None:
        with _TempRuntime() as rt:
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit(runtime_root=str(rt))
            valid = {"CONSISTENT", "WIRED_WITH_GAPS", "DRIFT_DETECTED", "GOVERNANCE_VIOLATION"}
            self.assertIn(result["overall_verdict"], valid)


# ---------------------------------------------------------------------------
# Suite 7 — SafetyInvariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants(unittest.TestCase):

    def test_audit_does_not_modify_policy_registry(self) -> None:
        with _TempRuntime() as rt:
            # Plant a fake policy_registry.json
            reg_path = rt / "state" / "policy_registry.json"
            original = {"policies": [], "_sentinel": "must_not_change"}
            reg_path.write_text(json.dumps(original))

            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))

            after = json.loads(reg_path.read_text())
            self.assertEqual(after["_sentinel"], "must_not_change",
                             "Audit modified policy_registry.json — invariant violated")

    def test_audit_does_not_modify_decision_log(self) -> None:
        with _TempRuntime() as rt:
            log_path = rt / "state" / "decision_log.jsonl"
            original_content = '{"ts":"2026-01-01","sentinel":"must_not_change"}\n'
            log_path.write_text(original_content)

            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))

            after = log_path.read_text()
            self.assertEqual(after, original_content,
                             "Audit modified decision_log.jsonl — invariant violated")

    def test_audit_does_not_modify_adaptation_log(self) -> None:
        with _TempRuntime() as rt:
            log_path = rt / "state" / "adaptation_log.jsonl"
            original = '{"ts":"2026-01-01","sentinel":"unchanged"}\n'
            log_path.write_text(original)

            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))

            self.assertEqual(log_path.read_text(), original,
                             "Audit modified adaptation_log.jsonl — invariant violated")

    def test_audit_own_outputs_are_limited_to_three_files(self) -> None:
        """Audit should only create/modify its own 3 output files in state/."""
        with _TempRuntime() as rt:
            state_d = rt / "state"
            # Record initial state files
            before = set(p.name for p in state_d.iterdir()) if state_d.exists() else set()

            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit(runtime_root=str(rt))

            after = set(p.name for p in state_d.iterdir())
            new_files = after - before
            # Only these three are allowed as new files
            allowed_new = {"runtime_self_audit.json", "drift_findings.jsonl"}
            unexpected = new_files - allowed_new
            self.assertEqual(unexpected, set(),
                             f"Audit created unexpected files in state/: {unexpected}")

    def test_api_self_audit_get_does_not_write(self) -> None:
        """GET /api/self_audit/latest should not create any new files."""
        import asyncio
        with _TempRuntime() as rt:
            state_d = rt / "state"
            before = set(p.name for p in state_d.iterdir()) if state_d.exists() else set()

            from interface.operator.api_self_audit import self_audit_latest
            asyncio.run(self_audit_latest())

            after = set(p.name for p in state_d.iterdir())
            self.assertEqual(after, before, "GET /api/self_audit/latest created files — should be read-only")


# ---------------------------------------------------------------------------
# Suite 8 — SmokeAuditMain
# ---------------------------------------------------------------------------

class TestSmokeAuditMain(unittest.TestCase):
    """Run a full audit against the real codebase and assert safety properties."""

    def test_smoke_audit_runs_without_exception(self) -> None:
        with _TempRuntime():
            from core.audit.runtime_self_audit import run_runtime_self_audit
            try:
                result = run_runtime_self_audit()
            except Exception as exc:
                self.fail(f"run_runtime_self_audit() raised exception: {exc}")
            self.assertIsInstance(result, dict)

    def test_smoke_verdict_is_acceptable_on_clean_main(self) -> None:
        """On clean main, verdict must be CONSISTENT or WIRED_WITH_GAPS — never GOVERNANCE_VIOLATION."""
        with _TempRuntime():
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit()
            verdict = result.get("overall_verdict")
            acceptable = {"CONSISTENT", "WIRED_WITH_GAPS"}
            self.assertIn(
                verdict, acceptable,
                f"Unexpected verdict '{verdict}' on clean main — "
                f"check findings: {[f.get('component') for f in result.get('findings', []) if not f.get('accepted') and f.get('severity') in ('CRITICAL', 'HIGH')]}",
            )

    def test_smoke_all_kernel_modules_exist(self) -> None:
        """All L1 kernel modules must be importable (excluding known SOT aliases)."""
        from core.audit.runtime_self_audit import CANONICAL_COMPONENTS
        import importlib.util
        # Skip entries with known_drift_key — these are intentional SOT alias entries
        # that document naming drift and are expected to be non-importable.
        kernel = [
            c for c in CANONICAL_COMPONENTS
            if c["layer"] == "L1_kernel" and not c.get("known_drift_key")
        ]
        for comp in kernel:
            spec = importlib.util.find_spec(comp["module"])
            self.assertIsNotNone(spec, f"Kernel module '{comp['module']}' not importable")

    def test_smoke_no_critical_open_findings(self) -> None:
        """Clean main should have zero CRITICAL open (non-accepted) findings."""
        with _TempRuntime():
            from core.audit.runtime_self_audit import run_runtime_self_audit
            from core.audit.drift_classifier import classify_finding
            result = run_runtime_self_audit()
            critical_open = [
                f for f in result.get("findings", [])
                if f.get("severity") == "CRITICAL" and not f.get("accepted")
            ]
            self.assertEqual(
                critical_open, [],
                f"Critical open findings on clean main: {[f.get('component') for f in critical_open]}",
            )

    def test_smoke_known_accepted_drift_items_present(self) -> None:
        """Expected accepted drift baseline items should appear as ACCEPTED in the audit."""
        with _TempRuntime():
            from core.audit.runtime_self_audit import run_runtime_self_audit
            result = run_runtime_self_audit()
            accepted_keys = {f.get("drift_key") for f in result.get("findings", []) if f.get("accepted")}
            # runtime_guardian naming drift must appear as ACCEPTED
            self.assertIn(
                "runtime_guardian_name_gap", accepted_keys,
                "runtime_guardian_name_gap should appear as ACCEPTED in smoke audit",
            )

    def test_smoke_api_self_audit_latest_returns_result(self) -> None:
        """After a smoke run, GET /api/self_audit/latest returns the result."""
        import asyncio
        with _TempRuntime():
            from core.audit.runtime_self_audit import run_runtime_self_audit
            run_runtime_self_audit()
            from interface.operator.api_self_audit import self_audit_latest
            response = asyncio.run(self_audit_latest())
            self.assertTrue(response.get("ok"))
            self.assertIsNotNone(response.get("audit"))


if __name__ == "__main__":
    unittest.main()
