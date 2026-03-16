"""AG-66 tests: Policy Promotion Workflow Hardening."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_full_workflow_runs(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.policy_workflow_hardening import run_review
    report = run_review("test_policy", "op1")
    assert report["workflow_id"]
    assert len(report["stages"]) == 5  # 4 stages + COMPLETE
    assert report["overall_status"] in ("PASS", "FAIL")


def test_stages_ordered(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.policy_workflow_hardening import run_review
    from runtime.policy_workflow_policy import WORKFLOW_STAGES
    report = run_review("test_policy", "op1")
    stage_names = [s["stage_name"] for s in report["stages"]]
    for expected in WORKFLOW_STAGES:
        assert expected in stage_names
    # Check order matches WORKFLOW_STAGES
    for i, stage in enumerate(WORKFLOW_STAGES):
        assert stage_names[i] == stage


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.policy_workflow_hardening import run_review
    run_review("test_policy", "op1")
    assert (tmp_path / "state" / "runtime_policy_workflow_latest.json").exists()
    assert (tmp_path / "state" / "runtime_policy_workflow_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_policy_workflow_index.json").exists()


def test_stages_have_evidence(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.policy_workflow_hardening import run_review
    report = run_review("test_policy", "op1")
    for stage in report["stages"]:
        assert "stage_name" in stage
        assert "status" in stage
        assert "result_summary" in stage
        assert "ts" in stage
