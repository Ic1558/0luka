from __future__ import annotations

from pathlib import Path


TEMPLATE = Path("/Users/icmini/0luka/interface/operator/templates/mission_control.html").read_text(encoding="utf-8")


def _system_model_section() -> str:
    marker = "<h2>System Model</h2>"
    start = TEMPLATE.index(marker)
    end = TEMPLATE.index("</section>", start)
    return TEMPLATE[start:end]


def test_system_model_section_renders_read_only_panel() -> None:
    section = _system_model_section()

    assert "System Model" in section
    assert 'id="system-model-panel"' in section
    assert 'id="system-model-status"' in section
    assert 'id="system-model-fields"' in section
    assert "System model unavailable" in section
    assert 'data-field="current_phase"' in section
    assert 'data-field="system_classification"' in section
    assert 'data-field="eligibility_to_act"' in section
    assert 'data-field="eligibility_reason"' in section
    assert 'data-field="repos_qs_boundary"' in section
    assert 'data-field="control_plane_enabled"' in section
    assert 'data-field="autonomy_enabled"' in section
    assert 'data-field="decision_memory_present"' in section


def test_system_model_fetch_wiring_is_present() -> None:
    assert "fetch('/api/system_model')" in TEMPLATE
    assert "renderSystemModel(payload);" in TEMPLATE
    assert "renderSystemModel(null);" in TEMPLATE
    assert "System model loaded" in TEMPLATE


def test_system_model_section_remains_read_only_and_has_no_controls() -> None:
    section = _system_model_section()

    assert "<button" not in section
    assert "<input" not in section
    assert "enqueueRemediationItem" not in section
    assert "submitApprovalAction" not in section
    assert "submitApprovalExpiry" not in section


def test_system_model_section_has_no_repos_qs_dependency() -> None:
    section = _system_model_section()

    assert "repos/qs Boundary" in section
    assert "fetch('/api/qs_runs" not in section
    assert "proof-artifact-panel" not in section


def _decision_desk_section() -> str:
    marker = "<h2>Decision Desk</h2>"
    start = TEMPLATE.index(marker)
    end = TEMPLATE.index("</section>", start)
    return TEMPLATE[start:end]


def test_decision_desk_section_renders_pending_fields() -> None:
    section = _decision_desk_section()

    assert 'id="decision-desk-panel"' in section
    assert 'id="decision-desk-status"' in section
    assert 'id="decision-desk-fields"' in section
    assert 'data-field="decision_id"' in section
    assert 'data-field="trace_id"' in section
    assert 'data-field="signal_received"' in section
    assert 'data-field="proposed_action"' in section
    assert 'data-field="evidence_refs"' in section
    assert 'data-field="ts_utc"' in section
    assert 'data-field="operator_status"' in section


def test_decision_desk_fetch_and_resolution_wiring_is_present() -> None:
    assert "fetch('/api/decisions/latest')" in TEMPLATE
    assert "fetch(endpoint, {" in TEMPLATE
    assert "/api/decisions/latest/approve" in TEMPLATE
    assert "/api/decisions/latest/reject" in TEMPLATE
    assert "submitDecisionResolution('approve')" in TEMPLATE
    assert "submitDecisionResolution('reject')" in TEMPLATE


def test_decision_desk_buttons_start_disabled_and_can_be_enabled_for_pending() -> None:
    section = _decision_desk_section()

    assert 'id="decision-approve"' in section
    assert 'id="decision-reject"' in section
    assert 'id="decision-operator-note"' in section
    assert 'disabled' in section
    assert "setDecisionActionState(true);" in TEMPLATE


def test_decision_desk_has_no_execution_or_remediation_actions() -> None:
    section = _decision_desk_section()

    assert "enqueueRemediationItem" not in section
    assert "submitApprovalAction" not in section
    assert "remediation_engine" not in TEMPLATE
    assert "task_dispatcher" not in TEMPLATE
