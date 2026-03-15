from __future__ import annotations

import copy

from core.result_reader import (
    detect_result_authority_mismatches,
    get_result_execution_events,
    get_result_executor_identity,
    get_result_policy,
    get_result_provenance_hashes,
    get_result_routing,
    get_result_seal,
    get_result_status,
    get_result_summary,
)


def _result_with_envelope(**overrides):
    base = {
        "status": "legacy-status",
        "summary": "legacy",
        "provenance": {"hashes": {"inputs_sha256": "legacy-input", "outputs_sha256": "legacy-output"}},
        "seal": {"alg": "hmac-sha256", "sig": "legacy"},
        "execution_envelope": {
            "result": {"status": "env-status", "summary": "env-summary"},
            "provenance": {
                "inputs_sha256": "env-input",
                "outputs_sha256": "env-output",
                "envelope_sha256": "env-envelope",
            },
            "seal": {"alg": "sha256", "value": "env-seal"},
            "evidence": {"execution_events": [{"event": "execution_started"}]},
            "executor": {"executor_id": "system/agents.lisa_executor.py", "executor_version": "lisa"},
            "routing": {"router": "core/router.py", "route": "lisa", "policy_version": "v1"},
            "policy": {"policy_id": "core/policy.yaml", "policy_version": "v1"},
        },
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def _result_without_envelope():
    return {
        "status": "legacy-status",
        "summary": "legacy",
        "provenance": {"hashes": {"inputs_sha256": "legacy-input", "outputs_sha256": "legacy-output"}},
        "seal": {"alg": "hmac-sha256", "sig": "legacy"},
    }


def test_helper_prefers_envelope_fields():
    result = _result_with_envelope()
    assert get_result_status(result) == "env-status"
    assert get_result_summary(result) == "env-summary"
    hashes = get_result_provenance_hashes(result)
    assert hashes["inputs_sha256"] == "env-input"
    assert hashes["outputs_sha256"] == "env-output"
    assert hashes["envelope_sha256"] == "env-envelope"
    assert get_result_seal(result)["value"] == "env-seal"
    assert get_result_executor_identity(result)["executor_id"] == "system/agents.lisa_executor.py"
    assert get_result_routing(result)["route"] == "lisa"
    assert get_result_policy(result)["policy_id"] == "core/policy.yaml"
    assert get_result_execution_events(result)


def test_helper_falls_back_without_envelope():
    result = _result_without_envelope()
    assert get_result_status(result) == "legacy-status"
    assert get_result_summary(result) == "legacy"
    hashes = get_result_provenance_hashes(result)
    assert hashes["inputs_sha256"] == "legacy-input"
    assert hashes["outputs_sha256"] == "legacy-output"
    assert hashes["envelope_sha256"] == ""
    assert get_result_seal(result)["sig"] == "legacy"
    assert get_result_execution_events(result) == []
    assert get_result_executor_identity(result) is None
    assert get_result_routing(result) is None
    assert get_result_policy(result) == {}


def test_mismatch_detection_reports_conflicts():
    result = _result_with_envelope()
    mismatches = detect_result_authority_mismatches(result)
    fields = {item["field"] for item in mismatches}
    assert {"status", "summary", "provenance.inputs_sha256", "provenance.outputs_sha256", "seal_schema"}.issubset(fields)
    seal_note = next(item for item in mismatches if item["field"] == "seal_schema")
    assert seal_note["kind"] == "informational"


def test_helpers_do_not_mutate_input():
    result = _result_with_envelope()
    copy_result = copy.deepcopy(result)
    get_result_status(result)
    get_result_summary(result)
    get_result_provenance_hashes(result)
    get_result_seal(result)
    get_result_execution_events(result)
    get_result_policy(result)
    assert result == copy_result
