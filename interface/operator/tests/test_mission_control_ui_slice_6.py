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
    assert 'data-field="execution_bridge_status"' in section
    assert 'data-field="execution_outcome_status"' in section
    assert 'data-field="execution_outcome_ref"' in section
    assert 'id="decision-suggestion-panel"' in section
    assert 'id="decision-suggestion-fields"' in section
    assert 'data-field="suggestion"' in section
    assert 'data-field="confidence_band"' in section
    assert 'data-field="confidence_score"' in section
    assert 'data-field="reason"' in section
    assert 'data-field="root_cause_hint"' in section


def test_decision_desk_fetch_and_resolution_wiring_is_present() -> None:
    assert "fetch('/api/decisions/latest')" in TEMPLATE
    assert "fetch('/api/decisions/latest/suggestion')" in TEMPLATE
    assert "fetch('/api/decisions/latest/suggestion-feedback')" in TEMPLATE
    assert "fetch(endpoint, {" in TEMPLATE
    assert "/api/decisions/latest/approve" in TEMPLATE
    assert "/api/decisions/latest/reject" in TEMPLATE
    assert "/api/decisions/latest/execute" in TEMPLATE
    assert "/api/decisions/latest/retry" in TEMPLATE
    assert "/api/decisions/latest/escalate" in TEMPLATE
    assert "submitDecisionResolution('approve')" in TEMPLATE
    assert "submitDecisionResolution('reject')" in TEMPLATE
    assert "submitDecisionExecution()" in TEMPLATE
    assert "submitDecisionRetry()" in TEMPLATE
    assert "submitDecisionEscalation()" in TEMPLATE
    assert "submitSuggestionIgnore()" in TEMPLATE
    assert "refreshDecisionSuggestion()" in TEMPLATE
    assert "refreshSuggestionFeedback()" in TEMPLATE


def test_decision_desk_buttons_start_disabled_and_can_be_enabled_for_pending() -> None:
    section = _decision_desk_section()

    assert 'id="decision-approve"' in section
    assert 'id="decision-reject"' in section
    assert 'id="decision-execute"' in section
    assert 'id="decision-retry"' in section
    assert 'id="decision-escalate"' in section
    assert 'id="decision-ignore-suggestion"' in section
    assert 'id="decision-operator-note"' in section
    assert 'disabled' in section
    assert "setDecisionActionState(true);" in TEMPLATE
    assert "function setDecisionExecuteState(enabled)" in TEMPLATE
    assert "function setDecisionRecoveryState(enabled)" in TEMPLATE


def test_decision_desk_has_no_execution_or_remediation_actions() -> None:
    section = _decision_desk_section()

    assert "enqueueRemediationItem" not in section
    assert "submitApprovalAction" not in section
    assert "remediation_engine" not in TEMPLATE
    assert "task_dispatcher" not in TEMPLATE
    assert "run anyway" not in TEMPLATE.lower()
    assert "automatic retry" not in TEMPLATE.lower()
    assert "background scheduler" not in TEMPLATE.lower()


def test_decision_desk_outcome_wording_distinguishes_handoff_from_completion() -> None:
    assert "Handoff accepted" in TEMPLATE
    assert "Waiting for confirmed outcome" in TEMPLATE
    assert "Execution succeeded" in TEMPLATE
    assert "Execution failed" in TEMPLATE
    assert "Outcome unknown" in TEMPLATE
    assert "Completion is not implied in this phase." in TEMPLATE


def test_decision_desk_recovery_controls_are_bounded_to_failed_or_unknown_outcomes() -> None:
    section = _decision_desk_section()

    assert 'data-field="execution_retry_count"' in section
    assert "Retry Execution" in section
    assert "Escalate Issue" in section
    assert "EXECUTION_FAILED" in TEMPLATE
    assert "EXECUTION_UNKNOWN" in TEMPLATE
    assert "Operator may retry or escalate this outcome." in TEMPLATE


def test_decision_desk_suggestion_panel_is_advisory_only() -> None:
    section = _decision_desk_section()

    assert "Suggested Action" in section
    assert "No Action Recommended" in section
    assert "Confidence" in section
    assert "Confidence Score" in section
    assert "No latest decision available." in section
    assert "Hint" in section
    assert "No latest decision available for suggestion analysis." in section
    assert "No suggestion feedback submitted." in section
    assert "No suggestion feedback recorded" in section
    assert "Retry Recommended" in TEMPLATE
    assert "Escalation Recommended" in TEMPLATE
    assert "High" in TEMPLATE
    assert "Medium" in TEMPLATE
    assert "Low" in TEMPLATE
    assert "Execution failed after approved decision." in TEMPLATE
    assert "Execution outcome is unknown after approved decision." in TEMPLATE
    assert "root_cause_hint" in TEMPLATE
    assert "renderDecisionSuggestion(payload)" in TEMPLATE
    assert 'id="decision-suggestion-feedback"' in section
    assert 'id="decision-suggestion-status"' in section
    assert "renderSuggestionFeedback(payload)" in TEMPLATE
