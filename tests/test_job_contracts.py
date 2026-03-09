from qs.app.jobs import ALLOWED_STATES, JOB_CONTRACTS, get_job_contract


def test_job_contracts_exist() -> None:
    assert {"boq_generate", "compliance_check", "po_generate"}.issubset(JOB_CONTRACTS.keys())


def test_po_generate_requires_approval() -> None:
    assert get_job_contract("po_generate").requires_approval is True


def test_contract_states_are_deterministic() -> None:
    assert ALLOWED_STATES == ("queued", "running", "success", "failed", "blocked")
