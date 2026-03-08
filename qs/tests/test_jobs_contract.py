from qs.app.jobs import JOB_DEFINITIONS, JobState, get_job_contract


def test_required_job_contracts_exist() -> None:
    assert {"boq_generate", "compliance_check", "po_generate"}.issubset(JOB_DEFINITIONS)


def test_po_generate_requires_approval() -> None:
    contract = get_job_contract("po_generate", "proj-1")
    assert contract.requires_approval is True


def test_job_contract_has_deterministic_allowed_states() -> None:
    contract = get_job_contract("boq_generate", "proj-1")
    assert contract.allowed_states == (
        JobState.QUEUED,
        JobState.RUNNING,
        JobState.WAITING_APPROVAL,
        JobState.SUCCEEDED,
        JobState.FAILED,
    )
