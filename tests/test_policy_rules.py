import pytest

from qs.app.policy import requires_approval


def test_policy_rules() -> None:
    assert requires_approval("boq_generate") is False
    assert requires_approval("compliance_check") is False
    assert requires_approval("po_generate") is True


def test_unknown_job_type_fails_closed() -> None:
    with pytest.raises(ValueError):
        requires_approval("unknown_job")
