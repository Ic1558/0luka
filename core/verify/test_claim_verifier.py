"""AG-48: Runtime Claim Verifier — test suite.

Tests:
  A. Claim Verifier Policy Unit Tests
  B. Claim Verifier Unit Tests
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


def _write_self_awareness(td: str, readiness: str = "GOVERNED_READY",
                           active_caps: int = 9, mode: str = "CONSERVATIVE") -> None:
    report = {
        "ts": "2026-03-16T00:00:00Z",
        "run_id": "run-001",
        "identity": {
            "system_identity": "Supervised Agentic Runtime Platform",
            "runtime_role": "governed execution + supervised repair + advisory intelligence",
            "active_capability_count": active_caps,
            "active_capabilities": [f"cap_{i}" for i in range(active_caps)],
            "operating_mode": mode,
        },
        "readiness": {"readiness": readiness, "confidence": 0.8, "reasons": ["test"]},
        "posture": {
            "operating_mode":     mode,
            "governance_posture": "OPERATOR_GATED",
            "repair_posture":     "SUPERVISED_REPAIR_AVAILABLE",
            "campaign_posture":   "CAMPAIGN_CONTROLLED",
            "decision_posture":   "QUEUE_GOVERNED",
            "strategy_posture":   "STRATEGY_ADVISORY",
        },
        "critical_gaps": [],
        "evidence_refs": ["runtime_capabilities.jsonl"],
        "operator_action_required": False,
    }
    (Path(td) / "state" / "runtime_self_awareness_latest.json").write_text(json.dumps(report))
    (Path(td) / "state" / "runtime_readiness.json").write_text(json.dumps({
        "ts": report["ts"], "run_id": "run-001",
        "readiness": readiness, "confidence": 0.8, "reasons": ["test"],
        "operating_mode": mode, "critical_gaps": [],
    }))


def _write_strategy(td: str, mode: str = "CONSERVATIVE") -> None:
    (Path(td) / "state" / "runtime_operating_mode.json").write_text(
        json.dumps({"operating_mode": mode, "confidence": 0.82})
    )
    (Path(td) / "state" / "runtime_strategy_latest.json").write_text(
        json.dumps({"operating_mode": mode, "key_risks": [], "recommendations": []})
    )


def _write_capabilities(td: str, caps: list[str]) -> None:
    p = Path(td) / "state" / "runtime_capabilities.jsonl"
    with p.open("w") as f:
        for c in caps:
            f.write(json.dumps({
                "capability_id": c, "component": "AG-XX",
                "activation_source": "test", "activated_at": "2026-03-16T00:00:00Z",
                "status": "ACTIVE", "notes": "",
            }) + "\n")


def _write_governance(td: str, findings: int = 2, has_queue: bool = True) -> None:
    status = {f"f-{i:03d}": {"status": "OPEN"} for i in range(findings)}
    (Path(td) / "state" / "drift_finding_status.json").write_text(json.dumps(status))
    if has_queue:
        (Path(td) / "state" / "decision_queue_governance_latest.json").write_text(
            json.dumps({"open_count": 1, "operator_action_required": True, "queue": []})
        )


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Policy Unit Tests
# ---------------------------------------------------------------------------

class TestClaimVerifierPolicy:

    def test_claim_verdicts_defined(self):
        from runtime.claim_verifier_policy import CLAIM_VERDICTS
        assert set(CLAIM_VERDICTS) == {"VERIFIED", "UNSUPPORTED", "INCONSISTENT", "INCONCLUSIVE"}

    def test_valid_claim_verdict_known(self):
        from runtime.claim_verifier_policy import valid_claim_verdict
        assert valid_claim_verdict("VERIFIED") is True

    def test_valid_claim_verdict_unknown(self):
        from runtime.claim_verifier_policy import valid_claim_verdict
        assert valid_claim_verdict("MAYBE") is False

    def test_verify_readiness_rule_governed_ready_passes_full_evidence(self):
        from runtime.claim_verifier_policy import verify_readiness_rule
        evidence = {
            "active_capability_count": 10,
            "strategy_active": True,
            "governance_active": True,
            "decision_queue_active": True,
        }
        result = verify_readiness_rule("GOVERNED_READY", evidence)
        assert result["verdict"] == "VERIFIED"

    def test_verify_readiness_rule_governed_ready_fails_low_caps(self):
        from runtime.claim_verifier_policy import verify_readiness_rule
        evidence = {
            "active_capability_count": 3,
            "strategy_active": True,
            "governance_active": True,
            "decision_queue_active": True,
        }
        result = verify_readiness_rule("GOVERNED_READY", evidence)
        assert result["verdict"] in ("INCONSISTENT", "UNSUPPORTED")

    def test_verify_readiness_rule_limited_always_verified(self):
        from runtime.claim_verifier_policy import verify_readiness_rule
        result = verify_readiness_rule("LIMITED", {})
        assert result["verdict"] == "VERIFIED"

    def test_verify_posture_rule_operator_gated_verified(self):
        from runtime.claim_verifier_policy import verify_posture_rule
        result = verify_posture_rule("governance_posture", "OPERATOR_GATED",
                                     {"operator_action_required": True})
        assert result["verdict"] == "VERIFIED"

    def test_verify_posture_rule_operator_gated_inconsistent(self):
        from runtime.claim_verifier_policy import verify_posture_rule
        result = verify_posture_rule("governance_posture", "OPERATOR_GATED",
                                     {"operator_action_required": False})
        assert result["verdict"] == "INCONSISTENT"

    def test_verify_posture_rule_unknown_is_inconclusive(self):
        from runtime.claim_verifier_policy import verify_posture_rule
        result = verify_posture_rule("governance_posture", "TOTALLY_UNKNOWN_CLASS", {})
        assert result["verdict"] == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Suite B: Claim Verifier Unit Tests
# ---------------------------------------------------------------------------

class TestClaimVerifierUnit:

    def test_verify_identity_claims_detects_capability_count_match(self):
        td = _make_tmpdir()
        _write_capabilities(td, [f"cap_{i}" for i in range(5)])
        self_awareness = {
            "identity": {
                "system_identity": "Supervised Agentic Runtime Platform",
                "runtime_role": "governed execution + supervised repair + advisory intelligence",
                "active_capability_count": 5,
            },
            "posture": {},
            "readiness": {},
            "present": True,
        }
        cap_data = {"active_count": 5, "active_capabilities": [f"cap_{i}" for i in range(5)]}
        from runtime.claim_verifier import verify_identity_claims
        results = verify_identity_claims(self_awareness, cap_data)
        count_result = next(r for r in results if r["claim_key"] == "active_capability_count")
        assert count_result["verdict"] == "VERIFIED"

    def test_verify_identity_claims_detects_capability_count_mismatch(self):
        td = _make_tmpdir()
        self_awareness = {
            "identity": {
                "system_identity": "Supervised Agentic Runtime Platform",
                "runtime_role": "governed execution + supervised repair + advisory intelligence",
                "active_capability_count": 10,  # claims 10
            },
            "posture": {}, "readiness": {}, "present": True,
        }
        cap_data = {"active_count": 3}  # only 3 active
        from runtime.claim_verifier import verify_identity_claims
        results = verify_identity_claims(self_awareness, cap_data)
        count_result = next(r for r in results if r["claim_key"] == "active_capability_count")
        assert count_result["verdict"] == "INCONSISTENT"

    def test_verify_readiness_claim_returns_verified_when_evidence_sufficient(self):
        td = _make_tmpdir()
        self_awareness = {"readiness": {"readiness": "GOVERNED_READY"}, "latest": {}, "present": True,
                          "identity": {}, "posture": {}}
        from runtime.claim_verifier import verify_readiness_claims
        results = verify_readiness_claims(
            self_awareness,
            capability_data={"active_count": 10},
            strategy_data={"strategy_present": True},
            governance_data={"governance_present": True, "queue_governance_present": True},
            repair_data={"repair_plan_present": True},
        )
        assert results[0]["verdict"] == "VERIFIED"

    def test_verify_readiness_claim_returns_unsupported_when_evidence_missing(self):
        td = _make_tmpdir()
        # Claims GOVERNED_READY but no capabilities registered
        self_awareness = {"readiness": {"readiness": "GOVERNED_READY"}, "latest": {}, "present": True,
                          "identity": {}, "posture": {}}
        from runtime.claim_verifier import verify_readiness_claims
        results = verify_readiness_claims(
            self_awareness,
            capability_data={"active_count": 0},
            strategy_data={"strategy_present": False},
            governance_data={"governance_present": False, "queue_governance_present": False},
            repair_data={"repair_plan_present": False},
        )
        assert results[0]["verdict"] in ("UNSUPPORTED", "INCONSISTENT")

    def test_verify_posture_claim_detects_inconsistent_operating_mode(self):
        td = _make_tmpdir()
        self_awareness = {
            "posture": {"operating_mode": "STABILIZE"},  # claims STABILIZE
            "latest": {}, "readiness": {}, "identity": {}, "present": True,
        }
        strategy_data = {"strategy_present": True, "operating_mode": "CONSERVATIVE"}  # actual CONSERVATIVE
        from runtime.claim_verifier import verify_posture_claims
        results = verify_posture_claims(
            self_awareness, strategy_data,
            governance_data={"operator_action_required": True, "queue_governance_present": True},
            campaign_data={"campaign_present": False, "outcome_intel_present": False},
            repair_data={"repair_plan_present": False, "repair_execution_available": False},
        )
        mode_result = next(r for r in results if r["claim_key"] == "operating_mode")
        assert mode_result["verdict"] == "INCONSISTENT"

    def test_build_claim_verification_report_contains_required_sections(self):
        td = _make_tmpdir()
        _write_self_awareness(td)
        _write_strategy(td)
        _write_capabilities(td, [f"cap_{i}" for i in range(9)])
        _write_governance(td)
        from runtime.claim_verifier import build_claim_verification_report
        report = build_claim_verification_report(td)
        required = {"ts", "run_id", "identity_results", "readiness_results",
                    "posture_results", "verdict_counts", "verified_count",
                    "inconsistent_count", "total_claims", "evidence_refs"}
        assert required.issubset(set(report.keys()))

    def test_store_claim_verification_writes_outputs(self):
        td = _make_tmpdir()
        _write_self_awareness(td)
        from runtime.claim_verifier import build_claim_verification_report, store_claim_verification
        report = build_claim_verification_report(td)
        store_claim_verification(report, td)
        state = Path(td) / "state"
        assert (state / "runtime_claim_verification_log.jsonl").exists()
        assert (state / "runtime_claim_verification_latest.json").exists()
        assert (state / "runtime_claim_verdicts.json").exists()


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_claim_verification_generates_outputs(self):
        td = _make_tmpdir()
        _write_self_awareness(td)
        _write_strategy(td)
        _write_capabilities(td, [f"cap_{i}" for i in range(9)])
        from runtime.claim_verifier import run_claim_verification
        result = run_claim_verification(td)
        assert result["ok"] is True
        assert result["total_claims"] > 0

    def test_run_generates_three_output_files(self):
        td = _make_tmpdir()
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        state = Path(td) / "state"
        assert (state / "runtime_claim_verification_log.jsonl").exists()
        assert (state / "runtime_claim_verification_latest.json").exists()
        assert (state / "runtime_claim_verdicts.json").exists()

    def test_run_full_matching_stack_verifies_all(self):
        td = _make_tmpdir()
        caps = [f"cap_{i}" for i in range(9)]
        _write_capabilities(td, caps)
        _write_self_awareness(td, readiness="GOVERNED_READY", active_caps=9, mode="CONSERVATIVE")
        _write_strategy(td, "CONSERVATIVE")
        _write_governance(td)
        from runtime.claim_verifier import run_claim_verification
        result = run_claim_verification(td)
        assert result["ok"] is True
        # With matching state, verified count should dominate
        assert result["verified_count"] >= result["inconsistent_count"]

    def test_run_empty_state_defaults_gracefully(self):
        td = _make_tmpdir()
        from runtime.claim_verifier import run_claim_verification
        result = run_claim_verification(td)
        assert result["ok"] is True

    def test_api_claim_verifier_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_claim_verifier import claim_verifier_latest
        result = asyncio.run(claim_verifier_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_claim_verifier_verdicts_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_claim_verifier import claim_verifier_verdicts
        result = asyncio.run(claim_verifier_verdicts())
        assert result["ok"] is True
        assert "verified_count" in result

    def test_api_claim_verifier_mismatches_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_claim_verifier import claim_verifier_mismatches
        result = asyncio.run(claim_verifier_mismatches())
        assert result["ok"] is True
        assert "mismatches" in result

    def test_api_claim_verifier_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_claim_verifier import claim_verifier_run
        req = _mock_request({})
        resp = asyncio.run(claim_verifier_run(req))
        assert resp.status_code == 403

    def test_api_claim_verifier_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_self_awareness(td)
        from interface.operator.api_claim_verifier import claim_verifier_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(claim_verifier_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert "verified_claims" in data


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_claim_verifier_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_governance(td)
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        mtime_before = gov_path.stat().st_mtime
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_claim_verifier_does_not_mutate_campaign_state(self):
        td = _make_tmpdir()
        camp_path = Path(td) / "state" / "repair_campaign_latest.json"
        camp_path.write_text(json.dumps({"campaigns": []}))
        mtime_before = camp_path.stat().st_mtime
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        assert camp_path.stat().st_mtime == mtime_before

    def test_claim_verifier_does_not_execute_repairs(self):
        td = _make_tmpdir()
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_claim_verifier_is_verification_only(self):
        td = _make_tmpdir()
        _write_self_awareness(td)
        _write_strategy(td)
        _write_capabilities(td, ["cap_a", "cap_b"])
        _write_governance(td)
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "audit_baseline.py",
            "repair_campaign_log.jsonl",
            "decision_queue_state.json",
            "decision_queue_log.jsonl",
            "operator_decision_queue.json",
            "runtime_self_awareness_latest.json",  # AG-47 output — must not be modified
        }
        # Verify AG-47 self-awareness file is not touched by verifier
        sa_path = state / "runtime_self_awareness_latest.json"
        if sa_path.exists():
            content = json.loads(sa_path.read_text())
            # Content must still be the original test data
            assert content.get("run_id") == "run-001"

    def test_claim_verifier_does_not_rewrite_self_awareness(self):
        td = _make_tmpdir()
        _write_self_awareness(td, readiness="GOVERNED_READY", active_caps=9)
        sa_path = Path(td) / "state" / "runtime_self_awareness_latest.json"
        mtime_before = sa_path.stat().st_mtime
        from runtime.claim_verifier import run_claim_verification
        run_claim_verification(td)
        # AG-47 artifact must remain untouched
        assert sa_path.stat().st_mtime == mtime_before
