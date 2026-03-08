from qs.app.jobs import JobState, get_job_contract
from qs.app.status import ActionBoundary, classify_action_boundary, emit_status


def test_emit_status_returns_deterministic_structure() -> None:
    contract = get_job_contract("compliance_check", "proj-1")
    payload = emit_status(
        contract=contract,
        state=JobState.RUNNING,
        action="inspect",
        detail="compliance running",
    )
    assert payload == {
        "job_type": "compliance_check",
        "project_id": "proj-1",
        "state": "running",
        "requires_approval": False,
        "action": "inspect",
        "action_boundary": "safe_read_only",
        "detail": "compliance running",
    }


def test_publish_actions_are_publish_finalize_boundary() -> None:
    contract = get_job_contract("boq_generate", "proj-1")
    assert classify_action_boundary(contract, "publish") == ActionBoundary.PUBLISH_FINALIZE


def test_po_generate_actions_are_approval_required_boundary() -> None:
    contract = get_job_contract("po_generate", "proj-1")
    assert classify_action_boundary(contract, "generate") == ActionBoundary.APPROVAL_REQUIRED
