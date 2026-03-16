"""AG-61 tests: Recommendation State Machine."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_legal_transitions(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_state_machine import create_recommendation, transition, get_state
    create_recommendation("rec_sm_001")
    transition("rec_sm_001", "VERIFIED")
    transition("rec_sm_001", "GATED")
    transition("rec_sm_001", "QUEUED")
    transition("rec_sm_001", "ACTIONED")
    transition("rec_sm_001", "RETAINED")
    transition("rec_sm_001", "CLOSED")
    assert get_state("rec_sm_001")["state"] == "CLOSED"


def test_illegal_transition_fails(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_state_machine import create_recommendation, transition
    create_recommendation("rec_sm_002")
    with pytest.raises(ValueError):
        transition("rec_sm_002", "ACTIONED")  # CREATED -> ACTIONED is illegal


def test_state_log_append_only(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_state_machine import create_recommendation, transition
    create_recommendation("rec_sm_003")
    transition("rec_sm_003", "VERIFIED")
    transition("rec_sm_003", "GATED")
    log = (tmp_path / "state" / "runtime_recommendation_state_log.jsonl").read_text().splitlines()
    assert len(log) == 3  # create + 2 transitions


def test_closed_is_terminal(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_state_machine import create_recommendation, transition
    create_recommendation("rec_sm_004")
    transition("rec_sm_004", "CLOSED")
    with pytest.raises(ValueError):
        transition("rec_sm_004", "VERIFIED")


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_state_machine import create_recommendation
    create_recommendation("rec_sm_005")
    assert (tmp_path / "state" / "runtime_recommendation_state_latest.json").exists()
    assert (tmp_path / "state" / "runtime_recommendation_state_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_recommendation_state_index.json").exists()
