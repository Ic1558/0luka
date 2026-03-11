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


def _policy_review_subsection() -> str:
    section = _decision_desk_section()
    marker = 'id="policy-review-panel"'
    start = section.index(marker)
    end = section.index("</div>", start)
    return section[start:end]


def _policy_tuning_subsection() -> str:
    section = _decision_desk_section()
    marker = 'id="policy-tuning-panel"'
    start = section.index(marker)
    end = section.index("</div>", start)
    return section[start:end]


def _policy_proposals_subsection() -> str:
    section = _decision_desk_section()
    marker = 'id="policy-proposals-panel"'
    start = section.index(marker)
    end = section.index('id="policy-version-panel"', start)
    return section[start:end]


def _policy_version_subsection() -> str:
    section = _decision_desk_section()
    marker = 'id="policy-version-panel"'
    start = section.index(marker)
    end = section.index("</div>", start)
    return section[start:end]


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
    assert 'data-field="execution_policy_status"' in section
    assert 'data-field="execution_policy_executed"' in section
    assert 'id="decision-suggestion-panel"' in section
    assert 'id="decision-suggestion-fields"' in section
    assert 'data-field="suggestion"' in section
    assert 'data-field="confidence_band"' in section
    assert 'data-field="confidence_score"' in section
    assert 'data-field="reason"' in section
    assert 'data-field="root_cause_hint"' in section
    assert 'data-field="policy_verdict"' in section
    assert 'data-field="policy_safe_lane"' in section
    assert 'data-field="policy_reason"' in section


def test_decision_desk_fetch_and_resolution_wiring_is_present() -> None:
    assert "fetch('/api/decisions/latest')" in TEMPLATE
    assert "fetch('/api/decisions/latest/suggestion')" in TEMPLATE
    assert "fetch('/api/decisions/latest/policy')" in TEMPLATE
    assert "fetch('/api/decisions/latest/suggestion-feedback')" in TEMPLATE
    assert "fetch('/api/policy/stats')" in TEMPLATE
    assert "fetch('/api/policy/review')" in TEMPLATE
    assert "fetch('/api/policy/tuning-preview" in TEMPLATE
    assert "fetch('/api/policy/proposals')" in TEMPLATE
    assert "fetch('/api/policy/proposals/' + encodeURIComponent(proposalId) + '/' + action" in TEMPLATE
    assert "fetch('/api/policy/proposals/' + encodeURIComponent(proposalId) + '/deploy'" in TEMPLATE
    assert "fetch('/api/policy/version')" in TEMPLATE
    assert "fetch('/api/policy/versions')" in TEMPLATE
    assert "fetch('/api/policy/versions/' + encodeURIComponent(policyVersionId) + '/rollback'" in TEMPLATE
    assert "fetch('/api/policy/auto-lane/unfreeze'" in TEMPLATE
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
    assert "AUTO RETRY TRIGGERED" in TEMPLATE
    assert "policy-executed retry" in TEMPLATE


def test_decision_desk_suggestion_panel_is_advisory_only() -> None:
    section = _decision_desk_section()

    assert "Suggested Action" in section
    assert "No Action Recommended" in section
    assert "Confidence" in section
    assert "Confidence Score" in section
    assert "No latest decision available." in section
    assert "Hint" in section
    assert "No latest decision available for suggestion analysis." in section
    assert "Policy" in section
    assert "Lane" in section
    assert "Policy Reason" in section
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
    assert "policyVerdictLabel(payload)" in TEMPLATE


def test_decision_desk_policy_panel_is_visibility_only() -> None:
    section = _decision_desk_section()

    assert "Auto Allowed" in TEMPLATE
    assert "Human Approval Required" in TEMPLATE
    assert "Manual Only" in TEMPLATE
    assert "Supervised Retry" in TEMPLATE
    assert "Supervised Escalation" in TEMPLATE
    assert "NONE" not in section
    assert 'data-field="policy_reason"' in section
    assert "policySafeLaneLabel(payload)" in TEMPLATE


def test_decision_desk_policy_stats_panel_is_observability_only() -> None:
    section = _decision_desk_section()

    assert 'id="policy-stats-panel"' in section
    assert 'id="policy-stats-status"' in section
    assert 'id="policy-stats-fields"' in section
    assert 'data-field="auto_retry_triggered"' in section
    assert 'data-field="success_rate"' in section
    assert 'data-field="operator_alignment_rate"' in section
    assert 'data-field="alignment_mismatch"' in section
    assert 'data-field="policy_state"' in section
    assert 'data-field="auto_lane_state"' in section
    assert 'data-field="auto_lane_reason"' in section
    assert 'data-field="auto_lane_lifecycle_event"' in section
    assert 'data-field="auto_lane_operator_note"' in section
    assert 'id="policy-auto-lane-note"' in section
    assert 'id="policy-auto-lane-unfreeze"' in section
    assert 'data-field="warning"' in section
    assert "Policy reliability degraded. Review recommended." in TEMPLATE
    assert "Auto retry is frozen; manual retry remains available." in TEMPLATE
    assert "Re-enable Auto Retry Lane" in TEMPLATE
    assert "submitPolicyAutoLaneUnfreeze()" in TEMPLATE
    assert "unfreezeButton.disabled = !isFrozen" in TEMPLATE
    assert "noteNode.disabled = !isFrozen" in TEMPLATE
    assert "renderPolicyStats(payload)" in TEMPLATE
    assert "refreshPolicyStats()" in TEMPLATE


def test_decision_desk_policy_review_panel_is_review_only() -> None:
    section = _policy_review_subsection()

    assert 'id="policy-review-panel"' in section
    assert 'id="policy-review-status"' in section
    assert 'id="policy-review-fields"' in section
    assert 'data-field="policy_state"' in section
    assert 'data-field="auto_lane_state"' in section
    assert 'data-field="policy_evaluations"' in section
    assert 'data-field="auto_retry_success_rate"' in section
    assert 'data-field="operator_alignment_rate"' in section
    assert 'data-field="review_summary"' in section
    assert 'id="policy-review-flags"' in section
    assert 'id="policy-review-reasons"' in section
    assert "insufficient evidence for strong review conclusions" in TEMPLATE
    assert "Policy review highlights areas for operator review only." in TEMPLATE
    assert "No review flags" in TEMPLATE
    assert "No policy reason breakdown available" in TEMPLATE
    assert "renderPolicyReview(payload)" in TEMPLATE
    assert "refreshPolicyReview()" in TEMPLATE
    assert "fetch('/api/policy/review')" in TEMPLATE
    assert "<button" not in section


def test_decision_desk_policy_tuning_panel_is_sandbox_only() -> None:
    section = _policy_tuning_subsection()

    assert 'id="policy-tuning-panel"' in section
    assert 'id="policy-tuning-status"' in section
    assert 'id="policy-tuning-fields"' in section
    assert 'data-field="baseline_threshold"' in section
    assert 'data-field="simulated_threshold"' in section
    assert 'data-field="baseline_retry_count"' in section
    assert 'data-field="simulated_retry_count"' in section
    assert 'data-field="baseline_success_rate"' in section
    assert 'data-field="simulated_success_rate"' in section
    assert 'data-field="retry_reduction"' in section
    assert 'data-field="expected_success_gain"' in section
    assert 'id="policy-tuning-threshold"' in section
    assert 'id="policy-tuning-run"' in section
    assert "Run Simulation" in section
    assert "runPolicyTuningPreview()" in TEMPLATE
    assert "Sandbox preview only. Live policy remains unchanged." in TEMPLATE
    assert "apply policy" not in section.lower()


def test_decision_desk_policy_proposals_panel_is_append_only_review_surface() -> None:
    section = _policy_proposals_subsection()

    assert 'id="policy-proposals-panel"' in section
    assert 'id="policy-proposals-status"' in section
    assert 'id="policy-proposal-component"' in section
    assert 'id="policy-proposal-value"' in section
    assert 'id="policy-proposal-note"' in section
    assert 'id="policy-proposal-create"' in section
    assert 'id="policy-proposals-list"' in section
    assert 'id="policy-proposal-detail-fields"' in section
    assert 'id="policy-proposal-action-note"' in section
    assert 'id="policy-proposal-approve"' in section
    assert 'id="policy-proposal-reject"' in section
    assert 'id="policy-proposal-deploy"' in section
    assert 'data-field="proposal_id"' in section
    assert 'data-field="policy_component"' in section
    assert 'data-field="current_value"' in section
    assert 'data-field="proposed_value"' in section
    assert 'data-field="status"' in section
    assert 'data-field="created_at"' in section
    assert "Create Proposal" in section
    assert "submitPolicyProposal()" in TEMPLATE
    assert "submitPolicyProposalAction('approve')" in TEMPLATE
    assert "submitPolicyProposalAction('reject')" in TEMPLATE
    assert "submitPolicyProposalDeploy()" in TEMPLATE
    assert "refreshPolicyProposals()" in TEMPLATE
    assert "refreshPolicyVersion()" in TEMPLATE
    assert "loadPolicyProposalDetail" in TEMPLATE
    assert "fetch('/api/policy/proposals/'" in TEMPLATE
    assert "Deploy Policy Change" in section
    assert "apply automatically" not in section.lower()


def test_decision_desk_live_policy_version_panel_is_read_only_deployment_surface() -> None:
    section = _policy_version_subsection()

    assert 'id="policy-version-panel"' in section
    assert 'id="policy-version-status"' in section
    assert 'id="policy-version-fields"' in section
    assert 'data-field="policy_component"' in section
    assert 'data-field="current_value"' in section
    assert 'data-field="policy_version_id"' in section
    assert 'data-field="deployed_at"' in section
    assert 'data-field="proposal_id"' in section
    assert 'data-field="rollback_of_version_id"' in section
    assert 'id="policy-version-history-status"' in section
    assert 'id="policy-version-history-list"' in section
    assert 'id="policy-version-rollback-note"' in section
    assert "Live Policy Version" in section
    assert "Live policy version loaded from explicit operator deployment." in TEMPLATE
    assert "No live policy version deployed beyond the default threshold." in TEMPLATE
    assert "Rollback creates a new active version using a previous value." in TEMPLATE
    assert "Rollback to This Version" in TEMPLATE
    assert "Current Active Version" in TEMPLATE
    assert "renderPolicyVersion(payload)" in TEMPLATE
    assert "refreshPolicyVersion()" in TEMPLATE
    assert "renderPolicyVersions(payload)" in TEMPLATE
    assert "refreshPolicyVersions()" in TEMPLATE
    assert "submitPolicyRollback(policyVersionId)" in TEMPLATE
