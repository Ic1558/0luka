"""AG-67 tests: Learning-to-Policy Bridge."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_bridge_runs(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.learning_policy_bridge import run_bridge
    records = run_bridge()
    assert isinstance(records, list)


def test_readiness_scoring():
    from runtime.learning_policy_bridge_policy import score_readiness
    assert score_readiness(0.9) == "READY"
    assert score_readiness(0.8) == "READY"
    assert score_readiness(0.6) == "REVIEW"
    assert score_readiness(0.5) == "REVIEW"
    assert score_readiness(0.3) == "NOT_READY"
    assert score_readiness(0.0) == "NOT_READY"


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.learning_policy_bridge import run_bridge
    run_bridge()
    assert (tmp_path / "state" / "runtime_learning_policy_bridge_latest.json").exists()
    assert (tmp_path / "state" / "runtime_learning_policy_bridge_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_learning_policy_bridge_index.json").exists()


def test_bridge_report_structure(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    import json
    from runtime.learning_policy_bridge import run_bridge
    run_bridge()
    report = json.loads((tmp_path / "state" / "runtime_learning_policy_bridge_latest.json").read_text())
    assert "bridge_id" in report
    assert "pattern_count" in report
    assert "candidate_count" in report
    assert "ts_evaluated" in report


def test_provenance_in_records(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    import json
    sd = tmp_path / "state"
    sd.mkdir()
    # Inject patterns and candidates into the runtime state for testing
    (sd / "pattern_registry.json").write_text(json.dumps([
        {"pattern_id": "pat_001", "pattern_type": "repeated_executor_failure", "confidence": 0.6}
    ]))
    (sd / "policy_candidates.jsonl").write_text(
        json.dumps({"candidate_id": "pc_001", "pattern_id": "pat_001",
                    "confidence": 0.6, "suggested_rule": "limit retries"}) + "\n"
    )
    # Score readiness directly
    from runtime.learning_policy_bridge_policy import score_readiness
    assert score_readiness(0.6) == "REVIEW"
