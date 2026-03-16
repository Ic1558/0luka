"""AG-72 tests: Sovereign Operator Mode."""
import os, sys, json
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_enter_sovereign_mode(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.sovereign_operator import enter_sovereign_mode
    session = enter_sovereign_mode("op_boss")
    assert isinstance(session, dict)
    assert "session_id" in session
    assert session["mode"] == "SOVEREIGN"
    assert session["operator_id"] == "op_boss"


def test_sovereign_capabilities_present(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.sovereign_operator import enter_sovereign_mode
    from runtime.sovereign_operator_policy import SOVEREIGN_CAPABILITIES
    session = enter_sovereign_mode("op_boss")
    for cap in SOVEREIGN_CAPABILITIES:
        assert cap in session["capabilities"]


def test_sovereign_runtime_state_keys(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.sovereign_operator import enter_sovereign_mode
    session = enter_sovereign_mode("op_boss")
    state = session["runtime_state"]
    for key in ["chain_execution", "decision_actions", "policy_review",
                "anomaly_handling", "replay", "self_audit_view", "governed_inference"]:
        assert key in state


def test_sovereign_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.sovereign_operator import enter_sovereign_mode
    enter_sovereign_mode("op_boss")
    assert (tmp_path / "state" / "runtime_sovereign_operator_latest.json").exists()
    assert (tmp_path / "state" / "runtime_sovereign_operator_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_sovereign_operator_index.json").exists()


def test_list_sovereign_sessions(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.sovereign_operator import enter_sovereign_mode, list_sovereign_sessions
    enter_sovereign_mode("op1")
    enter_sovereign_mode("op2")
    sessions = list_sovereign_sessions()
    assert len(sessions) == 2
