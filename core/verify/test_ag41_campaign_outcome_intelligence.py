"""AG-41: Repair Campaign Outcome Intelligence — test suite.

Tests:
  A. Campaign Pattern Registry Unit Tests
  B. Outcome Intelligence Unit Tests
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


def _write_campaign_log(td: str, campaigns: list[dict]) -> None:
    path = Path(td) / "state" / "repair_campaign_log.jsonl"
    with path.open("w") as fh:
        for c in campaigns:
            fh.write(json.dumps(c) + "\n")


def _write_recon_log(td: str, records: list[dict]) -> None:
    path = Path(td) / "state" / "repair_reconciliation_log.jsonl"
    with path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _successful_campaign(cid: str = "camp-001") -> dict:
    return {
        "campaign_id": cid,
        "findings_targeted": 3,
        "findings_resolved": 3,
        "total_waves": 2,
        "wave_abort_count": 0,
        "wave_pause_count": 0,
        "operator_intervention_count": 0,
        "regression_count": 0,
        "finding_ids": ["f-001", "f-002", "f-003"],
        "execution_ids": [],
    }


def _failed_campaign(cid: str = "camp-002") -> dict:
    return {
        "campaign_id": cid,
        "findings_targeted": 4,
        "findings_resolved": 1,
        "total_waves": 3,
        "wave_abort_count": 2,
        "wave_pause_count": 1,
        "operator_intervention_count": 4,
        "regression_count": 2,
        "finding_ids": ["f-010", "f-011", "f-012", "f-013"],
        "execution_ids": [],
    }


def _partial_campaign(cid: str = "camp-003") -> dict:
    return {
        "campaign_id": cid,
        "findings_targeted": 4,
        "findings_resolved": 2,
        "total_waves": 2,
        "wave_abort_count": 0,
        "wave_pause_count": 1,
        "operator_intervention_count": 1,
        "regression_count": 0,
        "finding_ids": ["f-020", "f-021", "f-022", "f-023"],
        "execution_ids": [],
    }


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Campaign Pattern Registry Unit Tests
# ---------------------------------------------------------------------------

class TestCampaignPatternRegistry:

    def test_outcome_classes_defined(self):
        from core.audit.campaign_pattern_registry import CAMPAIGN_OUTCOME_CLASSES
        required = {"CAMPAIGN_SUCCESS", "CAMPAIGN_PARTIAL", "CAMPAIGN_FAILED",
                    "CAMPAIGN_REGRESSION", "CAMPAIGN_INCONCLUSIVE"}
        assert required.issubset(set(CAMPAIGN_OUTCOME_CLASSES.keys()))

    def test_recommendation_classes_defined(self):
        from core.audit.campaign_pattern_registry import CAMPAIGN_RECOMMENDATION_CLASSES
        required = {"CONTINUE_PATTERN", "REVIEW_PATTERN", "RETIRE_PATTERN", "HIGH_RISK_PATTERN"}
        assert required.issubset(set(CAMPAIGN_RECOMMENDATION_CLASSES.keys()))

    def test_pattern_classes_minimum_seven(self):
        from core.audit.campaign_pattern_registry import CAMPAIGN_PATTERN_CLASSES
        required = {"repeatable_success_pattern", "high_intervention_pattern",
                    "regression_prone_pattern", "overlap_sensitive_pattern",
                    "pause_heavy_pattern", "abort_prone_pattern", "low_yield_pattern"}
        assert required.issubset(set(CAMPAIGN_PATTERN_CLASSES.keys()))

    def test_classify_campaign_patterns_success(self):
        from core.audit.campaign_pattern_registry import classify_campaign_patterns
        metrics = {
            "repair_success_rate": 0.95,
            "reconciliation_pass_ratio": 0.95,
            "regression_count": 0,
            "operator_intervention_count": 0,
            "wave_pause_count": 0,
            "wave_abort_count": 0,
            "total_waves": 2,
            "findings_resolved": 4,
            "findings_targeted": 4,
        }
        patterns = classify_campaign_patterns(metrics)
        assert "repeatable_success_pattern" in patterns

    def test_classify_campaign_patterns_regression_prone(self):
        from core.audit.campaign_pattern_registry import classify_campaign_patterns
        metrics = {
            "repair_success_rate": 0.4,
            "reconciliation_pass_ratio": 0.3,
            "regression_count": 3,
            "operator_intervention_count": 1,
            "wave_pause_count": 0,
            "wave_abort_count": 0,
            "total_waves": 2,
            "findings_resolved": 2,
            "findings_targeted": 5,
        }
        patterns = classify_campaign_patterns(metrics)
        assert "regression_prone_pattern" in patterns

    def test_classify_campaign_patterns_abort_prone(self):
        from core.audit.campaign_pattern_registry import classify_campaign_patterns
        metrics = {
            "repair_success_rate": 0.2,
            "reconciliation_pass_ratio": 0.2,
            "regression_count": 0,
            "operator_intervention_count": 2,
            "wave_pause_count": 0,
            "wave_abort_count": 3,
            "total_waves": 3,
            "findings_resolved": 1,
            "findings_targeted": 5,
        }
        patterns = classify_campaign_patterns(metrics)
        assert "abort_prone_pattern" in patterns

    def test_recommendation_for_pattern_returns_string(self):
        from core.audit.campaign_pattern_registry import recommendation_for_pattern
        assert recommendation_for_pattern("repeatable_success_pattern") == "CONTINUE_PATTERN"
        assert recommendation_for_pattern("regression_prone_pattern") == "HIGH_RISK_PATTERN"
        assert recommendation_for_pattern("abort_prone_pattern") == "RETIRE_PATTERN"


# ---------------------------------------------------------------------------
# Suite B: Outcome Intelligence Unit Tests
# ---------------------------------------------------------------------------

class TestOutcomeIntelligenceUnit:

    def test_score_campaign_effectiveness_returns_deterministic_score(self):
        from core.audit.repair_campaign_outcome_intelligence import score_campaign_effectiveness
        campaign = _successful_campaign()
        r1 = score_campaign_effectiveness(campaign)
        r2 = score_campaign_effectiveness(campaign)
        assert r1["effectiveness_score"] == r2["effectiveness_score"]
        assert r1["outcome_class"] == r2["outcome_class"]

    def test_score_successful_campaign_high_score(self):
        from core.audit.repair_campaign_outcome_intelligence import score_campaign_effectiveness
        result = score_campaign_effectiveness(_successful_campaign())
        assert result["effectiveness_score"] >= 60
        assert result["outcome_class"] in ("CAMPAIGN_SUCCESS", "CAMPAIGN_PARTIAL")

    def test_score_failed_campaign_low_score(self):
        from core.audit.repair_campaign_outcome_intelligence import score_campaign_effectiveness
        result = score_campaign_effectiveness(_failed_campaign())
        assert result["effectiveness_score"] < 60

    def test_score_contains_required_metrics(self):
        from core.audit.repair_campaign_outcome_intelligence import score_campaign_effectiveness
        result = score_campaign_effectiveness(_successful_campaign())
        required = {"campaign_id", "effectiveness_score", "outcome_class",
                    "repair_success_rate", "reconciliation_pass_ratio",
                    "regression_count", "operator_intervention_count",
                    "wave_abort_count", "total_waves", "findings_targeted",
                    "findings_resolved"}
        assert required.issubset(set(result.keys()))

    def test_detect_campaign_regressions_flags_failed_after_success(self):
        from core.audit.repair_campaign_outcome_intelligence import detect_campaign_regressions
        campaign = _failed_campaign()
        campaign["regression_count"] = 2
        recon = [
            {"finding_id": "f-010", "drift_recheck_result": "DRIFT_REGRESSED",
             "governance_recommendation": "recommend_HIGH_PRIORITY_ESCALATION"},
        ]
        regressions = detect_campaign_regressions([campaign], recon)
        assert len(regressions) >= 1
        assert regressions[0]["campaign_id"] == "camp-002"

    def test_detect_campaign_regressions_empty_for_clean_campaign(self):
        from core.audit.repair_campaign_outcome_intelligence import detect_campaign_regressions
        campaign = _successful_campaign()
        regressions = detect_campaign_regressions([campaign], [])
        assert regressions == []

    def test_detect_campaign_patterns_groups_repeatable_success(self):
        from core.audit.repair_campaign_outcome_intelligence import (
            score_campaign_effectiveness, detect_campaign_patterns
        )
        scored = [score_campaign_effectiveness(_successful_campaign(f"c{i}")) for i in range(3)]
        # Force repeatable success signals
        for s in scored:
            s["repair_success_rate"] = 0.95
            s["regression_count"] = 0
            s["operator_intervention_count"] = 0
            s["wave_abort_count"] = 0
            s["wave_pause_count"] = 0
        patterns = detect_campaign_patterns(scored)
        pattern_names = [p["pattern_class"] for p in patterns]
        assert "repeatable_success_pattern" in pattern_names

    def test_generate_campaign_outcome_report_contains_required_sections(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign(), _partial_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import generate_campaign_outcome_report
        report = generate_campaign_outcome_report(td)
        required = {"ts", "run_id", "campaign_count", "scored_campaigns", "regressions",
                    "patterns", "aggregate_effectiveness", "outcome_distribution",
                    "overall_recommendation", "operator_action_required"}
        assert required.issubset(set(report.keys()))
        assert report["operator_action_required"] is True

    def test_store_campaign_outcome_intelligence_writes_four_outputs(self):
        td = _make_tmpdir()
        from core.audit.repair_campaign_outcome_intelligence import (
            generate_campaign_outcome_report, store_campaign_outcome_intelligence
        )
        report = generate_campaign_outcome_report(td)
        store_campaign_outcome_intelligence(report, td)
        state = Path(td) / "state"
        assert (state / "repair_campaign_outcome_log.jsonl").exists()
        assert (state / "repair_campaign_outcome_latest.json").exists()
        assert (state / "campaign_effectiveness_score.json").exists()
        assert (state / "campaign_pattern_registry.json").exists()

    def test_regression_detection_uses_recon_history(self):
        td = _make_tmpdir()
        campaign = _successful_campaign("camp-reg")
        campaign["finding_ids"] = ["f-reg-01"]
        recon = [{"finding_id": "f-reg-01", "drift_recheck_result": "DRIFT_REGRESSED",
                  "governance_recommendation": "recommend_HIGH_PRIORITY_ESCALATION"}]
        from core.audit.repair_campaign_outcome_intelligence import detect_campaign_regressions
        regressions = detect_campaign_regressions([campaign], recon)
        assert any(r["campaign_id"] == "camp-reg" for r in regressions)


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_campaign_outcome_intelligence_generates_outputs(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign(), _failed_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        result = run_campaign_outcome_intelligence(td)
        assert result["ok"] is True
        assert result["campaign_count"] == 2

    def test_run_empty_campaign_history_returns_zero(self):
        td = _make_tmpdir()
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        result = run_campaign_outcome_intelligence(td)
        assert result["ok"] is True
        assert result["campaign_count"] == 0

    def test_run_generates_all_four_output_files(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        state = Path(td) / "state"
        assert (state / "repair_campaign_outcome_log.jsonl").exists()
        assert (state / "repair_campaign_outcome_latest.json").exists()
        assert (state / "campaign_effectiveness_score.json").exists()
        assert (state / "campaign_pattern_registry.json").exists()

    def test_api_campaign_outcome_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_campaign_outcome import campaign_outcome_latest
        result = asyncio.run(campaign_outcome_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_campaign_outcome_scores_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_campaign_outcome import campaign_outcome_scores
        result = asyncio.run(campaign_outcome_scores())
        assert result["ok"] is True
        assert "scored_campaigns" in result

    def test_api_campaign_outcome_patterns_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_campaign_outcome import campaign_outcome_patterns
        result = asyncio.run(campaign_outcome_patterns())
        assert result["ok"] is True
        assert "patterns" in result

    def test_api_campaign_outcome_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_campaign_outcome import campaign_outcome_run
        req = _mock_request({})
        resp = asyncio.run(campaign_outcome_run(req))
        assert resp.status_code == 403

    def test_api_campaign_outcome_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign(), _partial_campaign()])
        from interface.operator.api_campaign_outcome import campaign_outcome_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(campaign_outcome_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["campaign_count"] == 2


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_campaign_outcome_intelligence_does_not_mutate_campaign_state(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        campaign_path = Path(td) / "state" / "repair_campaign_log.jsonl"
        mtime_before = campaign_path.stat().st_mtime
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        mtime_after = campaign_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_campaign_outcome_intelligence_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_campaign_outcome_intelligence_does_not_modify_baseline(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_campaign_outcome_intelligence_is_analysis_only(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "drift_finding_status.json",
            "audit_baseline.py",
            # repair_campaign_log.jsonl is an INPUT written by the test helper — not forbidden
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_outputs_limited_to_ag41_files(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import run_campaign_outcome_intelligence
        run_campaign_outcome_intelligence(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "repair_campaign_log.jsonl",        # pre-existing input (not written by AG-41)
            "repair_campaign_outcome_log.jsonl",
            "repair_campaign_outcome_latest.json",
            "campaign_effectiveness_score.json",
            "campaign_pattern_registry.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_operator_action_required_always_true_in_report(self):
        td = _make_tmpdir()
        _write_campaign_log(td, [_successful_campaign()])
        from core.audit.repair_campaign_outcome_intelligence import generate_campaign_outcome_report
        report = generate_campaign_outcome_report(td)
        assert report["operator_action_required"] is True
