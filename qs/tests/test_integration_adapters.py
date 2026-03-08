from qs.app.jobs import get_job_contract
from qs.integration.oluka_policy import OlukaPolicyAdapter
from qs.integration.oluka_queue import OlukaQueueAdapter
from qs.integration.oluka_status import OlukaStatusAdapter


def test_queue_adapter_fails_closed_by_default() -> None:
    contract = get_job_contract("boq_generate", "proj-1")
    result = OlukaQueueAdapter().submit_job(contract)
    assert result.accepted is False


def test_policy_adapter_denies_approval_required_job_by_default() -> None:
    contract = get_job_contract("po_generate", "proj-1")
    result = OlukaPolicyAdapter().check_approval(contract)
    assert result.approved is False


def test_status_adapter_fails_closed_by_default() -> None:
    result = OlukaStatusAdapter().publish_status({"hello": "world"})
    assert result.published is False
