"""AG-42: Supervisory Runtime Strategy Layer — test suite.

Tests:
  A. Strategy Policy Unit Tests
  B. Strategy Layer Unit Tests
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


def _write_stability(td: str, score: int, classification: str) -> None:
    path = Path(td) / "state" / "runtime_stability_score.json"
    path.write_text(json.dumps({"score": score, "classification": classification}))


def _write_campaign_outcome(td: str, regressions: int = 0, avg_eff: float = 60.0,
                             failure_rate: float = 0.0) -> None:
    path = Path(td) / "state" / "repair_campaign_outcome_latest.json"
    path.write_text(json.dumps({
        "ts": "2026-03-16T00:00:00Z",
        "regressions": [{"campaign_id": f"c{i}"} for i in range(regressions)],
        "overall_recommendation": "HIGH_RISK_PATTERN" if regressions >= 2 else "REVIEW_PATTERN",
    }))
    scores_path = Path(td) / "state" / "campaign_effectiveness_score.json"
    scores_path.write_text(json.dumps({
        "aggregate_effectiveness": {
            "average_effectiveness_score": avg_eff,
            "total_regressions_detected": regressions,
        },
        "scored_campaigns": [],
    }))
    pattern_path = Path(td) / "state" / "campaign_pattern_registry.json"
    pattern_path.write_text(json.dumps({
        "patterns": [
            {"pattern_class": "regression_prone_pattern", "recommendation": "HIGH_RISK_PATTERN",
             "campaign_count": regressions}
        ] if regressions >= 2 else [],
        "overall_recommendation": "HIGH_RISK_PATTERN" if regressions >= 2 else "REVIEW_PATTERN",
    }))


def _write_priority_queue(td: str, p1: int = 0, p2: int = 0) -> None:
    queue = [{"finding_id": f"f-p1-{i}", "priority_class": "P1", "priority_score": 90}
             for i in range(p1)]
    queue += [{"finding_id": f"f-p2-{i}", "priority_class": "P2", "priority_score": 75}
              for i in range(p2)]
    path = Path(td) / "state" / "repair_priority_queue.json"
    path.write_text(json.dumps({"queue": queue}))
    latest_path = Path(td) / "state" / "repair_priority_latest.json"
    latest_path.write_text(json.dumps({"total_items": len(queue), "p1_count": p1, "p2_count": p2}))


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Strategy Policy Unit Tests
# ---------------------------------------------------------------------------

class TestStrategyPolicy:

    def test_operating_modes_minimum_defined(self):
        from core.audit.strategy_policy import OPERATING_MODES
        required = {"STABILIZE", "HIGH_RISK_HOLD", "GOVERNANCE_REVIEW", "CONSERVATIVE",
                    "THROUGHPUT_LIMITED", "PATTERN_REUSE_CANDIDATE", "REPAIR_FOCUSED"}
        assert required.issubset(set(OPERATING_MODES.keys()))

    def test_strategy_recommendations_minimum_defined(self):
        from core.audit.strategy_policy import STRATEGY_RECOMMENDATIONS
        required = {"CONTINUE_REPAIR_WAVE", "PAUSE_NEW_CAMPAIGNS", "REDUCE_WAVE_SIZE",
                    "REVIEW_PATTERN_BEFORE_REUSE", "ISOLATE_HIGH_RISK_COMPONENTS",
                    "PRIORITIZE_GOVERNANCE_FIXES"}
        assert required.issubset(set(STRATEGY_RECOMMENDATIONS.keys()))

    def test_classify_operating_mode_governance_risk(self):
        from core.audit.strategy_policy import classify_operating_mode
        mode = classify_operating_mode({
            "stability_classification": "GOVERNANCE_RISK",
            "stability_score": 10,
        })
        assert mode == "STABILIZE"

    def test_classify_operating_mode_high_risk_hold(self):
        from core.audit.strategy_policy import classify_operating_mode
        mode = classify_operating_mode({
            "stability_classification": "STABLE",
            "stability_score": 75,
            "active_regressions": 3,
        })
        assert mode == "HIGH_RISK_HOLD"

    def test_classify_operating_mode_conservative(self):
        from core.audit.strategy_policy import classify_operating_mode
        mode = classify_operating_mode({
            "stability_classification": "DEGRADED",
            "stability_score": 55,
            "active_regressions": 0,
        })
        assert mode == "CONSERVATIVE"

    def test_classify_operating_mode_repair_focused(self):
        from core.audit.strategy_policy import classify_operating_mode
        mode = classify_operating_mode({
            "stability_classification": "STABLE",
            "stability_score": 90,
            "p1_finding_count": 8,
            "active_regressions": 0,
            "regression_count": 0,
        })
        assert mode == "REPAIR_FOCUSED"

    def test_recommendation_priority_high_before_low(self):
        from core.audit.strategy_policy import recommendation_priority
        assert recommendation_priority("PAUSE_NEW_CAMPAIGNS") < recommendation_priority("CONTINUE_REPAIR_WAVE")


# ---------------------------------------------------------------------------
# Suite B: Strategy Layer Unit Tests
# ---------------------------------------------------------------------------

class TestStrategyLayerUnit:

    def test_derive_operating_mode_returns_conservative_on_regression(self):
        from core.audit.runtime_strategy_layer import derive_operating_mode
        stability = {"stability_score": 55, "stability_classification": "DEGRADED",
                     "hotspot_count": 2, "open_finding_count": 10}
        priority  = {"total_items": 5, "p1_count": 2, "p2_count": 3, "top_priority": None}
        outcomes  = {"campaign_count": 2, "avg_effectiveness_score": 40.0,
                     "campaign_failure_rate": 0.5, "active_regressions": 1,
                     "regression_count": 1, "operator_intervention_count": 2,
                     "high_risk_patterns": 0, "abort_prone_count": 0,
                     "overall_recommendation": "REVIEW_PATTERN"}
        result = derive_operating_mode(stability, priority, outcomes)
        assert result["operating_mode"] in ("CONSERVATIVE", "HIGH_RISK_HOLD", "STABILIZE",
                                             "GOVERNANCE_REVIEW", "THROUGHPUT_LIMITED")
        assert "operating_mode" in result
        assert "confidence" in result
        assert "reasons" in result
        assert isinstance(result["reasons"], list)

    def test_generate_strategy_recommendations_emits_pause_new_campaigns(self):
        from core.audit.runtime_strategy_layer import generate_strategy_recommendations
        stability   = {"stability_score": 30, "stability_classification": "GOVERNANCE_RISK",
                       "hotspot_count": 0, "open_finding_count": 5}
        priority    = {"total_items": 3, "p1_count": 2, "p2_count": 1, "top_priority": None}
        outcomes    = {"campaign_count": 1, "avg_effectiveness_score": 10.0,
                       "campaign_failure_rate": 0.8, "active_regressions": 3,
                       "regression_count": 3, "operator_intervention_count": 5,
                       "high_risk_patterns": 1, "abort_prone_count": 1,
                       "overall_recommendation": "HIGH_RISK_PATTERN"}
        drift_intel = {"pattern_count": 2, "patterns": [], "critical_patterns": []}
        recs = generate_strategy_recommendations("STABILIZE", stability, priority, outcomes, drift_intel)
        rec_names = [r["recommendation"] for r in recs]
        assert "PAUSE_NEW_CAMPAIGNS" in rec_names

    def test_generate_strategy_recommendations_emits_reduce_wave_size(self):
        from core.audit.runtime_strategy_layer import generate_strategy_recommendations
        stability   = {"stability_score": 45, "stability_classification": "DEGRADED",
                       "hotspot_count": 1, "open_finding_count": 8}
        priority    = {"total_items": 4, "p1_count": 1, "p2_count": 3, "top_priority": None}
        outcomes    = {"campaign_count": 2, "avg_effectiveness_score": 50.0,
                       "campaign_failure_rate": 0.3, "active_regressions": 0,
                       "regression_count": 0, "operator_intervention_count": 1,
                       "high_risk_patterns": 0, "abort_prone_count": 0,
                       "overall_recommendation": "REVIEW_PATTERN"}
        drift_intel = {"pattern_count": 1, "patterns": [], "critical_patterns": []}
        recs = generate_strategy_recommendations("CONSERVATIVE", stability, priority, outcomes, drift_intel)
        rec_names = [r["recommendation"] for r in recs]
        assert "REDUCE_WAVE_SIZE" in rec_names

    def test_build_runtime_strategy_report_contains_required_sections(self):
        td = _make_tmpdir()
        _write_stability(td, 80, "STABLE")
        from core.audit.runtime_strategy_layer import build_runtime_strategy_report
        report = build_runtime_strategy_report(td)
        required = {"ts", "run_id", "operating_mode", "mode_confidence", "mode_reasons",
                    "recommendations", "recommendation_count", "key_risks",
                    "stability_summary", "campaign_summary", "priority_summary",
                    "operator_action_required"}
        assert required.issubset(set(report.keys()))
        assert report["operator_action_required"] is True

    def test_store_runtime_strategy_writes_three_outputs(self):
        td = _make_tmpdir()
        _write_stability(td, 80, "STABLE")
        from core.audit.runtime_strategy_layer import build_runtime_strategy_report, store_runtime_strategy
        report = build_runtime_strategy_report(td)
        store_runtime_strategy(report, td)
        state = Path(td) / "state"
        assert (state / "runtime_strategy_latest.json").exists()
        assert (state / "runtime_strategy_log.jsonl").exists()
        assert (state / "runtime_operating_mode.json").exists()

    def test_recommendations_sorted_high_severity_first(self):
        td = _make_tmpdir()
        _write_stability(td, 20, "GOVERNANCE_RISK")
        _write_campaign_outcome(td, regressions=3)
        from core.audit.runtime_strategy_layer import build_runtime_strategy_report
        report = build_runtime_strategy_report(td)
        recs = report["recommendations"]
        if len(recs) >= 2:
            severity_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
            first_sev  = severity_order.get(recs[0]["severity"], 99)
            second_sev = severity_order.get(recs[1]["severity"], 99)
            assert first_sev <= second_sev

    def test_all_recommendations_have_operator_action_required(self):
        td = _make_tmpdir()
        _write_stability(td, 40, "CONSERVATIVE")
        from core.audit.runtime_strategy_layer import build_runtime_strategy_report
        report = build_runtime_strategy_report(td)
        for rec in report["recommendations"]:
            assert rec["operator_action_required"] is True


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_runtime_strategy_generates_outputs(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        result = run_runtime_strategy(td)
        assert result["ok"] is True
        assert result["operating_mode"] is not None

    def test_run_generates_all_three_output_files(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        state = Path(td) / "state"
        assert (state / "runtime_strategy_latest.json").exists()
        assert (state / "runtime_strategy_log.jsonl").exists()
        assert (state / "runtime_operating_mode.json").exists()

    def test_run_no_inputs_defaults_gracefully(self):
        td = _make_tmpdir()
        # No files at all — should not raise
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        result = run_runtime_strategy(td)
        assert result["ok"] is True

    def test_governance_risk_input_produces_stabilize_mode(self):
        td = _make_tmpdir()
        _write_stability(td, 10, "GOVERNANCE_RISK")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        result = run_runtime_strategy(td)
        assert result["operating_mode"] == "STABILIZE"

    def test_api_runtime_strategy_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_runtime_strategy import runtime_strategy_latest
        result = asyncio.run(runtime_strategy_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_runtime_strategy_mode_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_runtime_strategy import runtime_strategy_mode
        result = asyncio.run(runtime_strategy_mode())
        assert result["ok"] is True
        assert "operating_mode" in result

    def test_api_runtime_strategy_recommendations_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_runtime_strategy import runtime_strategy_recommendations
        result = asyncio.run(runtime_strategy_recommendations())
        assert result["ok"] is True
        assert "recommendations" in result

    def test_api_runtime_strategy_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_runtime_strategy import runtime_strategy_run
        req = _mock_request({})
        resp = asyncio.run(runtime_strategy_run(req))
        assert resp.status_code == 403

    def test_api_runtime_strategy_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_stability(td, 75, "STABLE")
        from interface.operator.api_runtime_strategy import runtime_strategy_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(runtime_strategy_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["operating_mode"] is not None


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_runtime_strategy_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        gov_path.write_text(json.dumps({"f-001": {"status": "ESCALATED"}}))
        mtime_before = gov_path.stat().st_mtime
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_runtime_strategy_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_runtime_strategy_does_not_modify_baseline(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_runtime_strategy_is_advisory_only(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "drift_finding_status.json",
            "audit_baseline.py",
            "repair_campaign_log.jsonl",
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_outputs_limited_to_ag42_files(self):
        td = _make_tmpdir()
        _write_stability(td, 70, "STABLE")
        from core.audit.runtime_strategy_layer import run_runtime_strategy
        run_runtime_strategy(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "runtime_stability_score.json",   # pre-existing input
            "runtime_strategy_latest.json",
            "runtime_strategy_log.jsonl",
            "runtime_operating_mode.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_operating_mode_is_recommendation_not_enforced(self):
        """Strategy report must carry operator_action_required=True always."""
        td = _make_tmpdir()
        _write_stability(td, 10, "GOVERNANCE_RISK")
        from core.audit.runtime_strategy_layer import build_runtime_strategy_report
        report = build_runtime_strategy_report(td)
        assert report["operator_action_required"] is True
