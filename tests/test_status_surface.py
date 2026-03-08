from qs.app.status import build_status_payload


def test_status_surface_is_deterministic() -> None:
    status = build_status_payload()
    assert status == {
        "service": "qs",
        "jobs_supported": ["boq_generate", "compliance_check", "po_generate"],
        "approval_required_jobs": ["po_generate"],
        "version": "phaseA",
    }
