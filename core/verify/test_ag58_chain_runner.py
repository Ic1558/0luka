"""AG-58: Tests for Mission Control Chain Runner."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, "/Users/icmini/0luka")


def test_all_chains_run(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.chain_runner import run_chain
    from runtime.chain_runner_policy import CHAIN_REGISTRY

    for chain_name in CHAIN_REGISTRY:
        report = run_chain(chain_name, "test_operator")
        assert report["overall_status"] in ("PASS", "PARTIAL", "FAIL"), \
            f"Chain {chain_name} returned unexpected status: {report['overall_status']}"
        assert "chain_id" in report
        assert "steps" in report
        assert isinstance(report["steps"], list)


def test_stop_on_fail(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime import chain_runner_policy, chain_runner

    def _fail_step():
        def run():
            return {"status": "FAIL", "summary": "injected failure", "artifacts": []}
        return run

    def _pass_step():
        def run():
            return {"status": "PASS", "summary": "should not run", "artifacts": []}
        return run

    # Inject a test chain
    original = chain_runner_policy.CHAIN_REGISTRY.copy()
    chain_runner_policy.CHAIN_REGISTRY["_test_fail_chain"] = [
        ("fail_step", _fail_step),
        ("should_not_run", _pass_step),
    ]

    try:
        report = chain_runner.run_chain("_test_fail_chain", "test_op")
        # Should stop after first step
        assert report["overall_status"] in ("FAIL", "PARTIAL")
        assert len(report["steps"]) == 1, f"Expected 1 step (stop on fail), got {len(report['steps'])}"
        assert report["steps"][0]["status"] == "FAIL"
    finally:
        chain_runner_policy.CHAIN_REGISTRY.clear()
        chain_runner_policy.CHAIN_REGISTRY.update(original)


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.chain_runner import run_chain
    from runtime.chain_runner_policy import CHAIN_REGISTRY

    chain_name = next(iter(CHAIN_REGISTRY))
    run_chain(chain_name, "test_op")

    state = tmp_path / "state"
    assert (state / "runtime_chain_runner_latest.json").exists()
    assert (state / "runtime_chain_runner_log.jsonl").exists()
    assert (state / "runtime_chain_runner_index.json").exists()


def test_chain_list():
    from runtime.chain_runner_policy import CHAIN_REGISTRY
    assert len(CHAIN_REGISTRY) >= 3
    assert "policy_review_chain" in CHAIN_REGISTRY
    assert "governance_review_chain" in CHAIN_REGISTRY
    assert "anomaly_learning_chain" in CHAIN_REGISTRY
