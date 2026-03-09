# 0luka Runtime v1 Seal

## Architecture Summary
0luka Runtime v1 is a policy-governed self-healing runtime with sealed governance, observability, remediation automation, and safety guardrails.

## Runtime Layers
- Kernel Runtime
- Governance Layer
- Observability Layer
- Autonomous Remediation
- Recovery Guardrails
- Proof Bundles
- Operator Audit UX

## Governance Enforcement
- Approval-gated remediation lanes
- Autonomy policy fail-closed evaluation
- Expiry and drift monitoring
- Audited approval and remediation history

## Autonomous Remediation System
- Remediation queue + self-healing worker
- Policy checks before execution
- Guardrail decisions recorded in runtime history

## Guardrails
- Rate limiting
- Retry limits
- Deterministic backoff
- Cooldown enforcement
- Loop protection

## Observability Endpoints
- /health
- /api/runtime_status
- /api/operator_status
- /api/activity
- /api/alerts
- /api/remediation_history
- /api/approval_log
- /api/runtime_decisions
- /api/autonomy_policy
- /api/approval_expiry
- /api/policy_drift
- /api/remediation_queue

## Verification Captured
- ============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /opt/homebrew/opt/python@3.14/bin/python3.14
cachedir: .pytest_cache
rootdir: /private/tmp/phase10_impl
plugins: anyio-4.12.1
collecting ... collected 460 items

core/verify/test_alert_api.py::test_alerts_endpoint_returns_valid_json PASSED [  0%]
core/verify/test_alert_api.py::test_alerts_are_parsed_from_alerts_jsonl PASSED [  0%]
core/verify/test_alert_api.py::test_ui_loads_without_error PASSED        [  0%]
core/verify/test_alert_daemon.py::test_daemon_can_run_single_evaluation_cycle PASSED [  0%]
core/verify/test_alert_daemon.py::test_daemon_writes_logs PASSED         [  1%]
core/verify/test_alert_daemon.py::test_daemon_triggers_alert_engine_execution PASSED [  1%]
core/verify/test_alert_daemon.py::test_daemon_exits_cleanly_on_interrupt PASSED [  1%]
core/verify/test_alert_engine.py::test_memory_critical_produces_critical_alert PASSED [  1%]
core/verify/test_alert_engine.py::test_redis_down_produces_critical_alert PASSED [  1%]
core/verify/test_alert_engine.py::test_healthy_runtime_produces_no_alert PASSED [  2%]
core/verify/test_alert_engine.py::test_alert_json_schema_validity PASSED [  2%]
core/verify/test_approval_expiry_monitor.py::test_missing_state_returns_ok_with_default_lanes PASSED [  2%]
core/verify/test_approval_expiry_monitor.py::test_detects_expired_and_expiring_soon PASSED [  2%]
core/verify/test_approval_expiry_monitor.py::test_api_returns_valid_json PASSED [  3%]
core/verify/test_approval_expiry_monitor.py::test_existing_endpoints_remain_functional PASSED [  3%]
core/verify/test_approval_history_api.py::test_approval_history_endpoint_returns_valid_json PASSED [  3%]
core/verify/test_approval_history_api.py::test_empty_approval_history_handled_safely PASSED [  3%]
core/verify/test_approval_history_api.py::test_approval_history_lane_filter_works PASSED [  3%]
core/verify/test_approval_history_api.py::test_recent_approval_history_entries_returned PASSED [  4%]
core/verify/test_approval_history_api.py::test_existing_endpoints_remain_functional PASSED [  4%]
core/verify/test_approval_hygiene.py::test_missing_approval_state_fails_closed PASSED [  4%]
core/verify/test_approval_hygiene.py::test_valid_future_expiry_keeps_approval_present PASSED [  4%]
core/verify/test_approval_hygiene.py::test_expired_approval_yields_approval_expired PASSED [  5%]
core/verify/test_approval_hygiene.py::test_expiring_soon_flag_set PASSED [  5%]
core/verify/test_approval_hygiene.py::test_malformed_timestamp_fails_closed_for_lane PASSED [  5%]
core/verify/test_approval_hygiene.py::test_unspecified_lane_remains_fail_closed PASSED [  5%]
core/verify/test_approval_hygiene.py::test_mission_control_api_returns_expiry_fields PASSED [  5%]
core/verify/test_approval_presets.py::test_list_presets_works PASSED     [  6%]
core/verify/test_approval_presets.py::test_apply_preset_writes_correct_events PASSED [  6%]
core/verify/test_approval_presets.py::test_reset_preset_writes_revoke_events PASSED [  6%]
core/verify/test_approval_presets.py::test_autonomy_policy_reflects_preset_effect PASSED [  6%]
core/verify/test_approval_presets.py::test_invalid_preset_rejected PASSED [  6%]
core/verify/test_approval_presets.py::test_approval_history_api_includes_preset_events PASSED [  7%]
core/verify/test_approval_write.py::test_approve_valid_lane PASSED       [  7%]
core/verify/test_approval_write.py::test_revoke_valid_lane PASSED        [  7%]
core/verify/test_approval_write.py::test_invalid_lane_fails PASSED       [  7%]
core/verify/test_approval_write.py::test_expiry_validation_fails_on_bad_format PASSED [  8%]
core/verify/test_approval_write.py::test_audit_log_entry_valid PASSED    [  8%]
core/verify/test_approval_write.py::test_mission_control_approval_endpoint_returns_valid_json PASSED [  8%]
core/verify/test_approval_write.py::test_unspecified_lanes_remain_fail_closed PASSED [  8%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_core_governance_is_hard_mode PASSED [  8%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_core_path_is_hard_mode PASSED [  9%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_github_workflows_is_hard_mode PASSED [  9%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_core_brain_is_med_mode PASSED [  9%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_tools_ops_is_med_mode PASSED [  9%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_modules_is_med_mode PASSED [ 10%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_docs_is_soft_mode PASSED [ 10%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_reports_is_soft_mode PASSED [ 10%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_observability_is_soft_mode PASSED [ 10%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_unknown_path_exits_4 PASSED [ 10%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_no_input_exits_4 PASSED [ 11%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_hard_path_in_core_governance_exits_4 PASSED [ 11%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_delete_core_governance_exits_4 PASSED [ 11%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_delete_workflow_exits_4 PASSED [ 11%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_hard_mode_has_required_checks PASSED [ 11%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_hard_mode_has_required_labels PASSED [ 12%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_med_mode_has_required_checks PASSED [ 12%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_soft_mode_minimal_checks PASSED [ 12%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_mixed_paths_uses_highest_ring PASSED [ 12%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_r2_and_r0_uses_r2 PASSED [ 13%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_json_output_has_required_fields PASSED [ 13%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_json_output_types PASSED [ 13%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_nl_infers_create_operation PASSED [ 13%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_nl_infers_edit_operation PASSED [ 13%]
core/verify/test_auto_governor_router.py::TestGovernorRouter::test_nl_extracts_path PASSED [ 14%]
core/verify/test_autonomy_policy.py::test_missing_approval_state_fails_closed PASSED [ 14%]
core/verify/test_autonomy_policy.py::test_valid_approval_state_allows_approved_lane PASSED [ 14%]
core/verify/test_autonomy_policy.py::test_expired_approval_requires_approval PASSED [ 14%]
core/verify/test_autonomy_policy.py::test_invalid_approval_file_fails_closed PASSED [ 15%]
core/verify/test_autonomy_policy.py::test_lane_filter_works PASSED       [ 15%]
core/verify/test_autonomy_policy.py::test_mission_control_api_returns_valid_json PASSED [ 15%]
core/verify/test_bridge.py::test_bridge_maps_task_shape PASSED           [ 15%]
core/verify/test_bridge.py::test_bridge_submits_into_core_inbox PASSED   [ 15%]
core/verify/test_build_sot_pack.py::test_preconditions_dirty_tree PASSED [ 16%]
core/verify/test_build_sot_pack.py::test_preconditions_seal_mismatch PASSED [ 16%]
core/verify/test_build_sot_pack.py::test_preconditions_clean PASSED      [ 16%]
core/verify/test_build_sot_pack.py::test_build_pack_success PASSED       [ 16%]
core/verify/test_build_sot_pack.py::test_anti_race_guard PASSED          [ 16%]
core/verify/test_circuit_breaker.py::test_closed_on_success PASSED       [ 17%]
core/verify/test_circuit_breaker.py::test_opens_after_threshold PASSED   [ 17%]
core/verify/test_circuit_breaker.py::test_half_open_after_timeout PASSED [ 17%]
core/verify/test_circuit_breaker.py::test_recovery_from_half_open PASSED [ 17%]
core/verify/test_circuit_breaker.py::test_error_status_counts_as_failure PASSED [ 18%]
core/verify/test_circuit_breaker.py::test_reset PASSED                   [ 18%]
core/verify/test_circuit_breaker.py::test_stats PASSED                   [ 18%]
core/verify/test_clec_gate.py::test_valid_clec_passes PASSED             [ 18%]
core/verify/test_clec_gate.py::test_invalid_op_rejected PASSED           [ 18%]
core/verify/test_clec_gate.py::test_unauthorized_run_blocked PASSED      [ 19%]
core/verify/test_clec_gate.py::test_evidence_capture PASSED              [ 19%]
core/verify/test_cli.py::test_cli_status_json PASSED                     [ 19%]
core/verify/test_cli.py::test_cli_submit_from_file PASSED                [ 19%]
core/verify/test_cli_ledger.py::test_cli_ledger_verify_returns_ok_json PASSED [ 20%]
core/verify/test_cli_ledger.py::test_cli_ledger_root_prints_current_root PASSED [ 20%]
core/verify/test_cli_ledger.py::test_cli_ledger_root_json_returns_raw_payload PASSED [ 20%]
core/verify/test_cli_ledger.py::test_cli_ledger_root_fails_when_runtime_root_missing PASSED [ 20%]
core/verify/test_cli_ledger.py::test_cli_ledger_root_fails_when_artifact_missing PASSED [ 20%]
core/verify/test_cole_run_integration.py::test_list_is_deterministic_sorted PASSED [ 21%]
core/verify/test_cole_run_integration.py::test_latest_uses_explicit_max_rule PASSED [ 21%]
core/verify/test_cole_run_integration.py::test_show_rejects_outside_scope_run_id PASSED [ 21%]
core/verify/test_cole_run_integration.py::test_show_redacts_sensitive_content PASSED [ 21%]
core/verify/test_cole_run_integration.py::test_no_write_or_network_patterns PASSED [ 21%]
core/verify/test_cole_run_integration.py::test_run_tool_has_explicit_cole_delegate PASSED [ 22%]
core/verify/test_config.py::test_config_defaults_to_repo_root PASSED     [ 22%]
core/verify/test_config.py::test_config_honors_root_env PASSED           [ 22%]
core/verify/test_config.py::test_config_requires_runtime_root_env PASSED [ 22%]
core/verify/test_dod_checker.py::test_designed_no_activity_with_reachable_commit PASSED [ 23%]
core/verify/test_dod_checker.py::test_unreachable_commit_sha_is_partial PASSED [ 23%]
core/verify/test_dod_checker.py::test_partial_missing_verified PASSED    [ 23%]
core/verify/test_dod_checker.py::test_partial_out_of_order_chain PASSED  [ 23%]
core/verify/test_dod_checker.py::test_partial_evidence_path_missing PASSED [ 23%]
core/verify/test_dod_checker.py::test_partial_evidence_path_traversal_rejected PASSED [ 24%]
core/verify/test_dod_checker.py::test_gate_blocks_proven_when_prereq_not_proven PASSED [ 24%]
core/verify/test_dod_checker.py::test_phase_id_and_phase_key_compatibility PASSED [ 24%]
core/verify/test_dod_checker.py::test_phase_id_preferred_over_phase_key PASSED [ 24%]
core/verify/test_dod_checker.py::test_proven_demo_fixture_exit_0 PASSED  [ 25%]
core/verify/test_dod_checker.py::test_exit_code_designed PASSED          [ 25%]
core/verify/test_dod_checker.py::test_exit_code_partial PASSED           [ 25%]
core/verify/test_dod_checker.py::test_exit_code_internal_error PASSED    [ 25%]
core/verify/test_dod_checker.py::test_update_status_phase_updates_only_target_phase PASSED [ 25%]
core/verify/test_dod_checker.py::test_update_status_phase_rejects_with_all PASSED [ 26%]
core/verify/test_dod_checker.py::test_update_status_phase_rejects_phase_missing PASSED [ 26%]
core/verify/test_dod_checker.py::test_update_status_phase_rejects_evidence_path_outside_repo PASSED [ 26%]
core/verify/test_dod_checker.py::test_all_ignores_fixture_for_exit_code PASSED [ 26%]
core/verify/test_dod_checker.py::test_fixture_phase_explicit_check_still_fails_when_missing_activity PASSED [ 26%]
core/verify/test_e2e_clec_pipeline.py::test_e2e_clec_write_text PASSED   [ 27%]
core/verify/test_e2e_clec_pipeline.py::test_e2e_clec_run_command PASSED  [ 27%]
core/verify/test_e2e_clec_pipeline.py::test_router_safe_rename_creates_parent_dirs PASSED [ 27%]
core/verify/test_e2e_clec_pipeline.py::test_audit_artifact_exists_on_ok PASSED [ 27%]
core/verify/test_e2e_clec_pipeline.py::test_audit_artifact_on_failure PASSED [ 28%]
core/verify/test_e2e_clec_pipeline.py::test_audit_no_hardpaths PASSED    [ 28%]
core/verify/test_e2e_clec_pipeline.py::test_audit_written_before_outbox_on_ok_path PASSED [ 28%]
core/verify/test_e2e_clec_pipeline.py::test_router_rejects_on_invalid_audit_payload PASSED [ 28%]
core/verify/test_e2e_clec_pipeline.py::test_audit_schema_conformance PASSED [ 28%]
core/verify/test_e2e_clec_pipeline.py::test_audit_rejects_invalid_decision PASSED [ 29%]
core/verify/test_epoch_emitter.py::test_genesis PASSED                   [ 29%]
core/verify/test_epoch_emitter.py::test_chain_continuity PASSED          [ 29%]
core/verify/test_epoch_emitter.py::test_epoch_hash_verification PASSED   [ 29%]
core/verify/test_epoch_emitter.py::test_dry_run PASSED                   [ 30%]
core/verify/test_epoch_emitter.py::test_missing_log PASSED               [ 30%]
core/verify/test_exported_proof.py::test_export_proof_pack_success PASSED [ 30%]
core/verify/test_exported_proof.py::test_verify_exported_proof_success PASSED [ 30%]
core/verify/test_exported_proof.py::test_tampered_checksum_fails PASSED  [ 30%]
core/verify/test_exported_proof.py::test_tampered_segment_chain_fails PASSED [ 31%]
core/verify/test_exported_proof.py::test_missing_ledger_root_fails PASSED [ 31%]
core/verify/test_exported_proof.py::test_stale_exported_head_fails PASSED [ 31%]
core/verify/test_exported_proof.py::test_deterministic_export_manifest_structure PASSED [ 31%]
core/verify/test_geometry_canonicalize.py::test_canonicalize_deterministic_hash_same_input PASSED [ 31%]
core/verify/test_geometry_canonicalize.py::test_canonicalize_hash_stable_under_vertex_rotation_and_polygon_order PASSED [ 32%]
core/verify/test_geometry_validator.py::test_validate_accepts_canonical_payload PASSED [ 32%]
core/verify/test_geometry_validator.py::test_validate_rejects_schema_version_mismatch PASSED [ 32%]
core/verify/test_geometry_validator.py::test_validate_rejects_non_canonical_unit PASSED [ 32%]
core/verify/test_geometry_validator.py::test_validate_rejects_non_numeric_vertex PASSED [ 33%]
core/verify/test_geometry_validator.py::test_validate_rejects_open_ring_when_closure_required PASSED [ 33%]
core/verify/test_geometry_validator.py::test_validate_rejects_area_below_minimum PASSED [ 33%]
core/verify/test_geometry_validator.py::test_validate_rejects_self_intersection PASSED [ 33%]
core/verify/test_geometry_validator.py::test_validate_rejects_adjacency_below_tolerance PASSED [ 33%]
core/verify/test_geometry_validator.py::test_validate_rejects_non_canonical_ordering_and_rounding PASSED [ 34%]
core/verify/test_geometry_validator.py::test_validate_errors_are_deterministically_ordered PASSED [ 34%]
core/verify/test_governance_contract.py::test_ring_classification PASSED [ 34%]
core/verify/test_governance_contract.py::test_core_never_imports_core_brain PASSED [ 34%]
core/verify/test_governance_contract.py::test_no_hard_paths_in_governance PASSED [ 35%]
core/verify/test_governance_contract.py::test_no_stale_copies PASSED     [ 35%]
core/verify/test_governance_contract.py::test_derived_files_declare_source PASSED [ 35%]
core/verify/test_governance_contract.py::test_cross_repo_manifest_no_hard_paths PASSED [ 35%]
core/verify/test_governance_contract.py::test_abi_frozen PASSED          [ 35%]
core/verify/test_governance_contract.py::test_governance_lock_manifest_consistent PASSED [ 36%]
core/verify/test_governance_contract.py::test_ontology_path_exists PASSED [ 36%]
core/verify/test_governance_file_lock.py::test_manifest_build_and_verify PASSED [ 36%]
core/verify/test_governance_file_lock.py::test_mutation_requires_label_and_manifest_refresh PASSED [ 36%]
core/verify/test_governance_file_lock.py::test_mutation_passes_with_label_and_manifest PASSED [ 36%]
core/verify/test_governance_proof.py::test_proof_mode_synthetic PASSED   [ 37%]
core/verify/test_governance_proof.py::test_proof_mode_operational PASSED [ 37%]
core/verify/test_governance_proof.py::test_taxonomy_incomplete PASSED    [ 37%]
core/verify/test_governance_proof.py::test_registry_integrity_check PASSED [ 37%]
core/verify/test_governance_proof.py::test_synthetic_detected_phase_15_5_3 PASSED [ 38%]
core/verify/test_health.py::test_health_returns_valid_report PASSED      [ 38%]
core/verify/test_health.py::test_health_reads_heartbeat PASSED           [ 38%]
core/verify/test_health.py::test_health_counts_queues PASSED             [ 38%]
core/verify/test_heartbeat_dropper.py::test_heartbeat_dropper_creates_jsonl_and_latest PASSED [ 38%]
core/verify/test_heartbeat_dropper.py::test_heartbeat_record_structure_and_constraints PASSED [ 39%]
core/verify/test_heartbeat_dropper.py::test_append_only_two_runs_two_lines_and_no_tmp_left PASSED [ 39%]
core/verify/test_idle_drift_monitor.py::test_healthy_exit_0 PASSED       [ 39%]
core/verify/test_idle_drift_monitor.py::test_idle_only_exit_2 PASSED     [ 39%]
core/verify/test_idle_drift_monitor.py::test_drift_only_exit_2 PASSED    [ 40%]
core/verify/test_idle_drift_monitor.py::test_both_exit_2 PASSED          [ 40%]
core/verify/test_idle_drift_monitor.py::test_parse_error_exit_4 PASSED   [ 40%]
core/verify/test_idle_drift_monitor.py::test_missing_log_exit_4 PASSED   [ 40%]
core/verify/test_ledger.py::test_ledger_append_and_query PASSED          [ 40%]
core/verify/test_ledger.py::test_ledger_deduplicates PASSED              [ 41%]
core/verify/test_ledger.py::test_ledger_rebuild_from_log PASSED          [ 41%]
core/verify/test_ledger.py::test_ledger_summary_correct PASSED           [ 41%]
core/verify/test_linguist_cli_v0.py::test_cli_happy_path_vector_001 FAILED [ 41%]
core/verify/test_linguist_cli_v0.py::test_cli_fail_closed_delete_all FAILED [ 41%]
core/verify/test_linguist_cli_v0.py::test_cli_preflight_fail_when_missing_activity_feed PASSED [ 42%]
core/verify/test_memory_recovery.py::test_healthy_non_critical_memory_noop PASSED [ 42%]
core/verify/test_memory_recovery.py::test_memory_critical_no_approval PASSED [ 42%]
core/verify/test_memory_recovery.py::test_memory_critical_no_safe_recovery_path PASSED [ 42%]
core/verify/test_memory_recovery.py::test_approved_memory_recovery_path_action_taken PASSED [ 43%]
core/verify/test_memory_recovery.py::test_remediation_log_schema_valid_and_scoped PASSED [ 43%]
core/verify/test_memory_recovery.py::test_remediation_engine_emits_memory_recovery_path PASSED [ 43%]
core/verify/test_merkle_root.py::test_genesis_root_creation_is_deterministic PASSED [ 43%]
core/verify/test_merkle_root.py::test_multi_leaf_root_is_stable PASSED   [ 43%]
core/verify/test_merkle_root.py::test_odd_leaf_duplication_rule PASSED   [ 44%]
core/verify/test_merkle_root.py::test_tampered_chain_hash_fails_verify PASSED [ 44%]
core/verify/test_merkle_root.py::test_segment_seq_disorder_fails_build PASSED [ 44%]
core/verify/test_merkle_root.py::test_head_mismatch_fails_verify PASSED  [ 44%]
core/verify/test_merkle_root.py::test_missing_ledger_root_fails_cleanly PASSED [ 45%]
core/verify/test_mission_control_server.py::test_health_endpoint_returns_ok PASSED [ 45%]
core/verify/test_mission_control_server.py::test_operator_status_endpoint_returns_json PASSED [ 45%]
core/verify/test_mission_control_server.py::test_runtime_status_endpoint_returns_json PASSED [ 45%]
core/verify/test_mission_control_server.py::test_activity_endpoint_returns_list PASSED [ 45%]
core/verify/test_operator_audit_api.py::test_audit_endpoints_return_valid_json PASSED [ 46%]
core/verify/test_operator_audit_api.py::test_entries_parse_correctly PASSED [ 46%]
core/verify/test_operator_audit_api.py::test_no_runtime_state_mutation PASSED [ 46%]
core/verify/test_operator_audit_api.py::test_existing_apis_remain_compatible PASSED [ 46%]
core/verify/test_operator_status_report.py::test_json_output_structure_valid PASSED [ 46%]
core/verify/test_operator_status_report.py::test_human_report_renders PASSED [ 47%]
core/verify/test_operator_status_report.py::test_missing_telemetry_file_handled_safely PASSED [ 47%]
core/verify/test_operator_status_report.py::test_degraded_memory_condition_detected PASSED [ 47%]
core/verify/test_operator_status_report.py::test_missing_ports_force_critical PASSED [ 47%]
core/verify/test_pack10_index_sovereignty.py::test_index_health_binds_to_feed_sha PASSED [ 48%]
core/verify/test_pack10_index_sovereignty.py::test_stale_index_triggers_auto_rebuild_in_query PASSED [ 48%]
core/verify/test_pack10_index_sovereignty.py::test_sovereign_emits_integrity_risk_when_sha_mismatch PASSED [ 48%]
core/verify/test_phase10_linguist.py::test_ambiguous_intent_requires_human_clarification PASSED [ 48%]
core/verify/test_phase10_linguist.py::test_clear_intent_does_not_trigger_clarification PASSED [ 48%]
core/verify/test_phase10_sentry.py::test_forbidden_secret_discovery_blocks_hard PASSED [ 49%]
core/verify/test_phase10_sentry.py::test_retry_loop_and_shell_escape_block_hard PASSED [ 49%]
core/verify/test_phase10_sentry.py::test_protected_target_warns_then_escalates PASSED [ 49%]
core/verify/test_phase10g_safe_wrappers.py::test_pytest_safe_warn_requires_force_then_allows FAILED [ 49%]
core/verify/test_phase10g_safe_wrappers.py::test_lint_safe_warn_requires_force_then_allows FAILED [ 50%]
core/verify/test_phase10h_verify_all_safe.py::test_verify_all_safe_exists PASSED [ 50%]
core/verify/test_phase10h_verify_all_safe.py::test_phase9_vectors_canonical_points_to_verify_all_safe PASSED [ 50%]
core/verify/test_phase11_audit.py::test_sanitization_and_no_leak PASSED  [ 50%]
core/verify/test_phase11_audit.py::test_injection_vector_neutralized_and_block_signal PASSED [ 50%]
core/verify/test_phase11_audit.py::test_observer_only_static_guard PASSED [ 51%]
core/verify/test_phase11b_schema_present_in_tmproot.py::test_clec_v1_schema_present_in_tmproot PASSED [ 51%]
core/verify/test_phase13_supervision.py::test_static_no_dispatcher_or_exec_calls PASSED [ 51%]
core/verify/test_phase13_supervision.py::test_annotation_append_and_schema_validation PASSED [ 51%]
core/verify/test_phase13_supervision.py::test_ui_has_ack_and_annotation_post_only PASSED [ 51%]
core/verify/test_phase13d_guard_telemetry_report.py::test_guard_telemetry_report_aggregates_and_redacts PASSED [ 52%]
core/verify/test_phase13d_guard_telemetry_report.py::test_guard_telemetry_report_uses_window_filter PASSED [ 52%]
core/verify/test_phase14_learning_metrics.py::test_static_safety_scan PASSED [ 52%]
core/verify/test_phase14_learning_metrics.py::test_metrics_and_recommendations_parsing PASSED [ 52%]
core/verify/test_phase15_1_skill_wiring.py::test_reject_missing_manifest_or_mandatory_ingest PASSED [ 53%]
core/verify/test_phase15_1_skill_wiring.py::test_pass_when_manifest_and_mandatory_ingest_present PASSED [ 53%]
core/verify/test_phase15_1_skill_wiring.py::test_ingest_emits_skill_ingestrunner_provenance PASSED [ 53%]
core/verify/test_phase15_2_codex_wiring.py::test_missing_execution_contract_rejected_fail_closed PASSED [ 53%]
core/verify/test_phase15_2_codex_wiring.py::test_invalid_manifest_wiring_rejected_fail_closed PASSED [ 53%]
core/verify/test_phase15_2_codex_wiring.py::test_mandatory_skill_with_ingest_and_contract_emits_provenance PASSED [ 54%]
core/verify/test_phase15_3_pattern_killer.py::test_detect_finds_matches_deterministically PASSED [ 54%]
core/verify/test_phase15_3_pattern_killer.py::test_rewrite_supports_empty_replacement_deterministically PASSED [ 54%]
core/verify/test_phase15_3_pattern_killer.py::test_score_is_stable PASSED [ 54%]
core/verify/test_phase15_3_pattern_killer.py::test_schema_validation_rejects_bad_jsonl_lines PASSED [ 55%]
core/verify/test_phase15_3_pattern_killer.py::test_e2e_detect_rewrite_score_apply PASSED [ 55%]
core/verify/test_phase15_4_skill_aliases.py::test_extra_usage_alias_resolves PASSED [ 55%]
core/verify/test_phase15_4_skill_aliases.py::test_alias_normalization_variants_resolve PASSED [ 55%]
core/verify/test_phase15_4_skill_aliases.py::test_unknown_skill_error_contains_required_fields PASSED [ 55%]
core/verify/test_phase15_4_skill_aliases.py::test_ambiguous_alias_rejected_deterministically PASSED [ 56%]
core/verify/test_phase15_4_skill_aliases.py::test_alias_resolution_emits_provenance_row PASSED [ 56%]
core/verify/test_phase15_4_skill_aliases.py::test_alias_preserves_mandatory_ingest_interlock PASSED [ 56%]
core/verify/test_phase15_5_2_timeline_heartbeat.py::test_heartbeat_emit_success PASSED [ 56%]
core/verify/test_phase15_5_2_timeline_heartbeat.py::test_heartbeat_emit_failure_non_fatal PASSED [ 56%]
core/verify/test_phase15_5_2_timeline_heartbeat.py::test_heartbeat_emit_rejected PASSED [ 57%]
core/verify/test_phase15_5_4_operational_proof.py::test_operational_chain_from_monitor_is_accepted PASSED [ 57%]
core/verify/test_phase15_5_4_operational_proof.py::test_synthetic_chain_rejected_when_operational_required PASSED [ 57%]
core/verify/test_phase15_5_4_operational_proof.py::test_missing_taxonomy_keys_flagged PASSED [ 57%]
core/verify/test_phase15_5_4_operational_proof.py::test_parse_failure_exits_4_in_operational_mode PASSED [ 58%]
core/verify/test_phase15_skill_os.py::test_manifest_exists PASSED        [ 58%]
core/verify/test_phase15_skill_os.py::test_manifest_has_required_columns PASSED [ 58%]
core/verify/test_phase15_skill_os.py::test_mandatory_read_detectable PASSED [ 58%]
core/verify/test_phase15_skill_os.py::test_skill_files_exist PASSED      [ 58%]
core/verify/test_phase15_skill_os.py::test_chain_contract_documented PASSED [ 59%]
core/verify/test_phase1c_gate.py::test_ref_only_ok PASSED                [ 59%]
core/verify/test_phase1c_gate.py::test_hard_path_reject PASSED           [ 59%]
core/verify/test_phase1c_gate.py::test_injected_resolved_reject PASSED   [ 59%]
core/verify/test_phase1c_gate.py::test_unknown_ref_reject PASSED         [ 60%]
core/verify/test_phase1c_gate.py::test_traversal_reject PASSED           [ 60%]
core/verify/test_phase1d_result_gate.py::test_ok_plain PASSED            [ 60%]
core/verify/test_phase1d_result_gate.py::test_redact_users_log PASSED    [ 60%]
core/verify/test_phase1d_result_gate.py::test_side_effect_without_evidence_fail_closed PASSED [ 60%]
core/verify/test_phase1d_result_gate.py::test_error_message_sanitized PASSED [ 61%]
core/verify/test_phase1d_result_gate.py::test_back_resolve_trusted_uri PASSED [ 61%]
core/verify/test_phase1d_result_gate.py::test_schema_missing_task_id_reject PASSED [ 61%]
core/verify/test_phase1e_outbox_writer.py::test_atomic_write_and_schema PASSED [ 61%]
core/verify/test_phase1e_outbox_writer.py::test_missing_status_reject PASSED [ 61%]
core/verify/test_phase1e_outbox_writer.py::test_ok_without_evidence_becomes_partial PASSED [ 62%]
core/verify/test_phase2_1_reasoning.py::test_protected_escalates_and_blocks_headless PASSED [ 62%]
core/verify/test_phase2_1_reasoning.py::test_internal_local_read_file_path PASSED [ 62%]
core/verify/test_phase2_1_reasoning.py::test_reflect_promotes_to_confirmed_and_freezes PASSED [ 62%]
core/verify/test_phase2_evidence.py::test_missing_provenance_hard_fails PASSED [ 63%]
core/verify/test_phase2_evidence.py::test_deterministic_hash_for_same_input PASSED [ 63%]
core/verify/test_phase2_evidence.py::test_execution_events_and_append_only_artifact PASSED [ 63%]
core/verify/test_phase8_dispatcher.py::test_entrypoint_watch_loop_runs PASSED [ 63%]
core/verify/test_phase8_dispatcher.py::test_launchd_plist_exists_and_logs_declared PASSED [ 63%]
core/verify/test_phase8_dispatcher.py::test_dispatch_emits_execution_events_and_run_provenance PASSED [ 64%]
core/verify/test_phase8_dispatcher.py::test_reboot_survival_simulated_restart_picks_task PASSED [ 64%]
core/verify/test_phase9_nlp.py::test_canonical_clec_v1_shape PASSED      [ 64%]
core/verify/test_phase9_nlp.py::test_protected_requires_human_escalate PASSED [ 64%]
core/verify/test_phase9_nlp.py::test_forbidden_secret_discovery_hard_fails PASSED [ 65%]
core/verify/test_phase9_nlp.py::test_local_task_through_dispatcher_has_provenance PASSED [ 65%]
core/verify/test_phase9_vectors.py::test_phase9_vectors_validate PASSED  [ 65%]
core/verify/test_phase_growth_guard.py::test_detect_new_phase_from_diff PASSED [ 65%]
core/verify/test_phase_growth_guard.py::test_validate_new_phase_pass PASSED [ 65%]
core/verify/test_phase_growth_guard.py::test_validate_new_phase_fail_missing_proof PASSED [ 66%]
core/verify/test_phase_growth_guard.py::test_detect_new_module_name_from_diff PASSED [ 66%]
core/verify/test_policy_drift_detector.py::test_no_drift_detected PASSED [ 66%]
core/verify/test_policy_drift_detector.py::test_approval_log_mismatch_detected PASSED [ 66%]
core/verify/test_policy_drift_detector.py::test_expired_approval_detected PASSED [ 66%]
core/verify/test_policy_drift_detector.py::test_unknown_lane_detected PASSED [ 67%]
core/verify/test_policy_drift_detector.py::test_api_endpoint_returns_valid_json PASSED [ 67%]
core/verify/test_policy_drift_detector.py::test_mission_control_panel_loads PASSED [ 67%]
core/verify/test_proof_bundle_builder.py::test_bundle_directory_created PASSED [ 67%]
core/verify/test_proof_bundle_builder.py::test_all_expected_files_present PASSED [ 68%]
core/verify/test_proof_bundle_builder.py::test_sha256_file_contains_valid_hashes PASSED [ 68%]
core/verify/test_proof_bundle_builder.py::test_bundle_generation_does_not_mutate_source_files PASSED [ 68%]
core/verify/test_proof_report.py::test_valid_proof_pack_human_report_verified PASSED [ 68%]
core/verify/test_proof_report.py::test_valid_proof_pack_json_ok_true PASSED [ 68%]
core/verify/test_proof_report.py::test_tampered_checksum_fails_with_failed_output PASSED [ 69%]
core/verify/test_proof_report.py::test_missing_required_file_fails_cleanly PASSED [ 69%]
core/verify/test_proof_report.py::test_stale_head_root_mismatch_fails_cleanly PASSED [ 69%]
core/verify/test_proof_report.py::test_deterministic_json_keys_and_shape PASSED [ 69%]
core/verify/test_publish_notebooklm_gate.py::test_publish_gate_aborts_on_dirty_tree PASSED [ 70%]
core/verify/test_publish_notebooklm_gate.py::test_publish_gate_aborts_on_hash_mismatch PASSED [ 70%]
core/verify/test_publish_notebooklm_gate.py::test_publish_gate_succeeds_with_perfect_seal PASSED [ 70%]
core/verify/test_publish_notebooklm_gate.py::test_publish_gate_does_not_mutate_tracked_files PASSED [ 70%]
core/verify/test_recovery_guardrails.py::test_rate_limit_triggers_after_threshold PASSED [ 70%]
core/verify/test_recovery_guardrails.py::test_retry_limit_triggers_after_max_attempts PASSED [ 71%]
core/verify/test_recovery_guardrails.py::test_backoff_values_correct_for_attempts PASSED [ 71%]
core/verify/test_recovery_guardrails.py::test_cooldown_blocks_repeated_execution PASSED [ 71%]
core/verify/test_recovery_guardrails.py::test_loop_protection_halts_repeated_failures PASSED [ 71%]
core/verify/test_recovery_guardrails.py::test_healthy_execution_path_still_succeeds PASSED [ 71%]
core/verify/test_recovery_guardrails.py::test_self_healing_worker_respects_guardrail_denial PASSED [ 72%]
core/verify/test_recovery_guardrails.py::test_no_mutation_outside_queue_guardrail_history_state PASSED [ 72%]
core/verify/test_remediation_daemon.py::test_once_mode_runs_one_cycle PASSED [ 72%]
core/verify/test_remediation_daemon.py::test_daemon_mode_logs_started_cycle_stopped PASSED [ 72%]
core/verify/test_remediation_daemon.py::test_transient_remediation_failure_does_not_kill_daemon_loop PASSED [ 73%]
core/verify/test_remediation_daemon.py::test_keyboard_interrupt_exits_cleanly PASSED [ 73%]
core/verify/test_remediation_daemon.py::test_remediation_daemon_log_content_valid PASSED [ 73%]
core/verify/test_remediation_engine.py::test_healthy_state_noop FAILED   [ 73%]
core/verify/test_remediation_engine.py::test_api_missing_no_approval FAILED [ 73%]
core/verify/test_remediation_engine.py::test_redis_missing_no_approval FAILED [ 74%]
core/verify/test_remediation_engine.py::test_memory_critical_manual_intervention_required FAILED [ 74%]
core/verify/test_remediation_engine.py::test_configured_action_path_unavailable FAILED [ 74%]
core/verify/test_remediation_engine.py::test_remediation_log_schema_valid PASSED [ 74%]
core/verify/test_remediation_engine.py::test_approved_api_restart_action_taken FAILED [ 75%]
core/verify/test_remediation_history_api.py::test_remediation_history_endpoint_returns_valid_json PASSED [ 75%]
core/verify/test_remediation_history_api.py::test_empty_remediation_history_handled_safely PASSED [ 75%]
core/verify/test_remediation_history_api.py::test_lane_filter_works FAILED [ 75%]
core/verify/test_remediation_history_api.py::test_recent_timeline_entries_returned PASSED [ 75%]
core/verify/test_remediation_history_api.py::test_existing_endpoints_remain_functional PASSED [ 76%]
core/verify/test_remediation_policy.py::test_healthy_system_noop PASSED  [ 76%]
core/verify/test_remediation_policy.py::test_memory_failure_first_attempt_uses_priority FAILED [ 76%]
core/verify/test_remediation_policy.py::test_retry_attempt_after_cooldown FAILED [ 76%]
core/verify/test_remediation_policy.py::test_cooldown_active PASSED      [ 76%]
core/verify/test_remediation_policy.py::test_escalation_triggered PASSED [ 77%]
core/verify/test_remediation_policy.py::test_remediation_log_schema_valid PASSED [ 77%]
core/verify/test_remediation_queue.py::test_enqueue_item PASSED          [ 77%]
core/verify/test_remediation_queue.py::test_queue_state_transition PASSED [ 77%]
core/verify/test_remediation_queue.py::test_invalid_queue_request_rejected PASSED [ 78%]
core/verify/test_remediation_queue.py::test_queue_api_returns_correct_json PASSED [ 78%]
core/verify/test_remediation_reconciliation.py::test_successful_memory_recovery_resets_attempts PASSED [ 78%]
core/verify/test_remediation_reconciliation.py::test_successful_worker_recovery_resets_attempts PASSED [ 78%]
core/verify/test_remediation_reconciliation.py::test_healthy_lane_clears_stale_state PASSED [ 78%]
core/verify/test_remediation_reconciliation.py::test_failing_lane_does_not_clear_state_prematurely PASSED [ 79%]
core/verify/test_remediation_reconciliation.py::test_reconciliation_log_schema_valid PASSED [ 79%]
core/verify/test_remediation_reconciliation.py::test_reconciliation_scoped_to_state_and_log_files PASSED [ 79%]
core/verify/test_remediation_reporting.py::test_empty_log_summary_valid PASSED [ 79%]
core/verify/test_remediation_reporting.py::test_log_with_recovery_counts_correct PASSED [ 80%]
core/verify/test_remediation_reporting.py::test_lane_filter_works PASSED [ 80%]
core/verify/test_remediation_reporting.py::test_json_output_valid PASSED [ 80%]
core/verify/test_remediation_reporting.py::test_last_n_filtering_works PASSED [ 80%]
core/verify/test_remediation_reporting.py::test_no_mutation_of_runtime_state PASSED [ 80%]
core/verify/test_retention.py::test_log_rotation_triggers_on_size PASSED [ 81%]
core/verify/test_retention.py::test_log_rotation_skips_small_file PASSED [ 81%]
core/verify/test_retention.py::test_dir_age_respects_keep_min PASSED     [ 81%]
core/verify/test_retention.py::test_protected_paths_never_deleted PASSED [ 81%]
core/verify/test_retention.py::test_dry_run_deletes_nothing PASSED       [ 81%]
core/verify/test_retention.py::test_activity_feed_emits_important_events_no_hardpaths PASSED [ 82%]
core/verify/test_runtime_lane_v0.py::test_runtime_lane_positive_submit PASSED [ 82%]
core/verify/test_runtime_lane_v0.py::test_runtime_lane_enqueue_submit PASSED [ 82%]
core/verify/test_runtime_lane_v0.py::test_runtime_lane_reject_fail_closed PASSED [ 82%]
core/verify/test_runtime_status_report.py::test_healthy_path_with_all_sources_available PASSED [ 83%]
core/verify/test_runtime_status_report.py::test_proof_pack_unavailable_is_degraded PASSED [ 83%]
core/verify/test_runtime_status_report.py::test_watchdog_fail_is_failed PASSED [ 83%]
core/verify/test_runtime_status_report.py::test_health_fail_is_failed PASSED [ 83%]
core/verify/test_runtime_status_report.py::test_human_output_contains_required_sections PASSED [ 83%]
core/verify/test_runtime_status_report.py::test_json_contract_shape_is_deterministic PASSED [ 84%]
core/verify/test_seal.py::test_sign_and_verify PASSED                    [ 84%]
core/verify/test_seal.py::test_tampered_fails_verify PASSED              [ 84%]
core/verify/test_seal.py::test_compute_hmac_deterministic PASSED         [ 84%]
core/verify/test_seal.py::test_chain_ledger_entry PASSED                 [ 85%]
core/verify/test_seal.py::test_chain_integrity PASSED                    [ 85%]
core/verify/test_seal.py::test_no_seal_fails_verify PASSED               [ 85%]
core/verify/test_segment_chain.py::test_segment_chain_genesis_append PASSED [ 85%]
core/verify/test_segment_chain.py::test_segment_chain_continuity_two_entries PASSED [ 85%]
core/verify/test_segment_chain.py::test_duplicate_segment_rejected PASSED [ 86%]
core/verify/test_segment_chain.py::test_duplicate_seal_rejected PASSED   [ 86%]
core/verify/test_segment_chain.py::test_chain_fork_and_seq_mismatch_rejected PASSED [ 86%]
core/verify/test_segment_chain.py::test_invalid_segment_name_rejected PASSED [ 86%]
core/verify/test_segment_chain.py::test_audit_detects_chain_hash_mismatch PASSED [ 86%]
core/verify/test_segment_chain.py::test_audit_detects_missing_registry_entry PASSED [ 87%]
core/verify/test_segment_chain.py::test_audit_detects_missing_segment_file PASSED [ 87%]
core/verify/test_self_healing_worker.py::test_queue_item_executed_successfully PASSED [ 87%]
core/verify/test_self_healing_worker.py::test_policy_block_respected PASSED [ 87%]
core/verify/test_self_healing_worker.py::test_approval_missing_blocked PASSED [ 88%]
core/verify/test_self_healing_worker.py::test_state_transitions_correct PASSED [ 88%]
core/verify/test_self_healing_worker.py::test_remediation_history_logged PASSED [ 88%]
core/verify/test_self_healing_worker.py::test_queue_updated_correctly PASSED [ 88%]
core/verify/test_sentry_v0.py::test_preflight_pass_minimal PASSED        [ 88%]
core/verify/test_sentry_v0.py::test_preflight_fail_missing_root PASSED   [ 89%]
core/verify/test_sentry_v0.py::test_preflight_fail_git_index_lock PASSED [ 89%]
core/verify/test_sentry_v0.py::test_probe_dispatcher_fail_when_launchctl_not_running PASSED [ 89%]
core/verify/test_sentry_v0.py::test_probe_dispatcher_fail_when_state_not_running PASSED [ 89%]
core/verify/test_smoke.py::test_smoke_clean_passes PASSED                [ 90%]
core/verify/test_smoke.py::test_smoke_result_schema PASSED               [ 90%]
core/verify/test_submit.py::test_submit_flat_task PASSED                 [ 90%]
core/verify/test_submit.py::test_submit_with_explicit_task_id PASSED     [ 90%]
core/verify/test_submit.py::test_submit_rejects_duplicate PASSED         [ 90%]
core/verify/test_submit.py::test_submit_rejects_hard_paths PASSED        [ 91%]
core/verify/test_submit.py::test_submit_native_envelope PASSED           [ 91%]
core/verify/test_task_dispatcher.py::test_dispatch_clec_task_e2e PASSED  [ 91%]
core/verify/test_task_dispatcher.py::test_dispatch_emits_start_end_events PASSED [ 91%]
core/verify/test_task_dispatcher.py::test_dispatch_idempotent PASSED     [ 91%]
core/verify/test_task_dispatcher.py::test_dispatch_invalid_yaml_is_quarantined PASSED [ 92%]
core/verify/test_task_dispatcher.py::test_dispatch_non_clec_skipped PASSED [ 92%]
core/verify/test_task_dispatcher.py::test_dispatch_hard_path_rejected PASSED [ 92%]
core/verify/test_task_dispatcher.py::test_dispatch_runtime_guard_rejects_non_template_root PASSED [ 92%]
core/verify/test_task_dispatcher.py::test_dispatch_guard_telemetry_missing_required_fields PASSED [ 93%]
core/verify/test_task_dispatcher.py::test_dispatch_guard_telemetry_root_absolute_no_echo PASSED [ 93%]
core/verify/test_task_dispatcher.py::test_dispatch_guard_valid_task_no_blocked_event PASSED [ 93%]
core/verify/test_task_dispatcher.py::test_dispatch_rejects_resolved_injection_and_resolves_ref PASSED [ 93%]
core/verify/test_task_dispatcher.py::test_dispatch_writes_latest_pointer PASSED [ 93%]
core/verify/test_task_dispatcher.py::test_dispatch_pointer_schema_conformance PASSED [ 94%]
core/verify/test_task_dispatcher.py::test_submit_dispatch_round_trip PASSED [ 94%]
core/verify/test_task_dispatcher.py::test_watch_mode_cycles PASSED       [ 94%]
core/verify/test_task_dispatcher.py::test_watch_heartbeat_no_hardpaths PASSED [ 94%]
core/verify/test_tier3_abi.py::test_abi_file_loads PASSED                [ 95%]
core/verify/test_tier3_abi.py::test_exit_code_semantics_preserved PASSED [ 95%]
core/verify/test_tier3_abi.py::test_invalid_verdict_name_triggers_failure PASSED [ 95%]
core/verify/test_tier3_abi.py::test_missing_proof_requirement_triggers_failure PASSED [ 95%]
core/verify/test_tier3_abi.py::test_fixture_exclusion_still_works PASSED [ 95%]
core/verify/test_timeline.py::test_emit_creates_timeline PASSED          [ 96%]
core/verify/test_timeline.py::test_emit_appends_events PASSED            [ 96%]
core/verify/test_timeline.py::test_read_empty_timeline PASSED            [ 96%]
core/verify/test_timeline.py::test_emit_with_detail PASSED               [ 96%]
core/verify/test_tool_selection_policy.py::test_scenario_a_protected PASSED [ 96%]
core/verify/test_tool_selection_policy.py::test_scenario_b_local PASSED  [ 97%]
core/verify/test_tool_selection_policy.py::test_scenario_c_reflect_update PASSED [ 97%]
core/verify/test_tool_selection_policy.py::test_scenario_d_runtime_bootstrap_and_legacy_detection PASSED [ 97%]
core/verify/test_tool_selection_policy.py::test_scenario_e_legacy_path_reference_emits_event PASSED [ 97%]
core/verify/test_watchdog.py::test_heartbeat_missing PASSED              [ 98%]
core/verify/test_watchdog.py::test_heartbeat_fresh PASSED                [ 98%]
core/verify/test_watchdog.py::test_stuck_tasks_detected PASSED           [ 98%]
core/verify/test_watchdog.py::test_tmp_cleanup PASSED                    [ 98%]
core/verify/test_worker_recovery.py::test_healthy_bridge_workers_noop PASSED [ 98%]
core/verify/test_worker_recovery.py::test_bridge_failure_no_approval PASSED [ 99%]
core/verify/test_worker_recovery.py::test_bridge_failure_no_safe_recovery_path PASSED [ 99%]
core/verify/test_worker_recovery.py::test_approved_worker_recovery_path_action_taken PASSED [ 99%]
core/verify/test_worker_recovery.py::test_remediation_log_schema_valid_and_scoped PASSED [ 99%]
core/verify/test_worker_recovery.py::test_remediation_engine_emits_worker_recovery_path PASSED [100%]

=================================== FAILURES ===================================
________________________ test_cli_happy_path_vector_001 ________________________

    def test_cli_happy_path_vector_001() -> None:
        cp = _run_cli("Create file notes/today.txt with text 'hello team'", root=REPO_ROOT)
>       assert cp.returncode == 0, cp.stderr or cp.stdout
E       AssertionError: {"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_4b4bb99ffb76496b928c264006f3a495"}
E         
E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['python3', '-m', 'core.linguist_cli', '--input', "Create file notes/today.txt with text 'hello team'"], returncode=1, stdout='{"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_4b4bb99ffb76496b928c264006f3a495"}\n', stderr='').returncode

core/verify/test_linguist_cli_v0.py:22: AssertionError
_______________________ test_cli_fail_closed_delete_all ________________________

    def test_cli_fail_closed_delete_all() -> None:
        cp = _run_cli("ลบไฟล์ทั้งหมดในโปรเจกต์", root=REPO_ROOT)
>       assert cp.returncode == 2, cp.stderr or cp.stdout
E       AssertionError: {"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_18069d88e06640bfa1b1d8689f09c833"}
E         
E       assert 1 == 2
E        +  where 1 = CompletedProcess(args=['python3', '-m', 'core.linguist_cli', '--input', '\u0e25\u0e1a\u0e44\u0e1f\u0e25\u0e4c\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14\u0e43\u0e19\u0e42\u0e1b\u0e23\u0e40\u0e08\u0e01\u0e15\u0e4c'], returncode=1, stdout='{"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_18069d88e06640bfa1b1d8689f09c833"}\n', stderr='').returncode

core/verify/test_linguist_cli_v0.py:32: AssertionError
_______________ test_pytest_safe_warn_requires_force_then_allows _______________

    def test_pytest_safe_warn_requires_force_then_allows() -> None:
        blocked = _run(["bash", "tools/ops/pytest_safe.zsh", "--no-refresh"], force_level="WARN")
>       assert blocked.returncode == 41, blocked.stdout + blocked.stderr
E       AssertionError: safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json
E         
E       assert 43 == 41
E        +  where 43 = CompletedProcess(args=['bash', 'tools/ops/pytest_safe.zsh', '--no-refresh'], returncode=43, stdout='', stderr='safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json\n').returncode

core/verify/test_phase10g_safe_wrappers.py:22: AssertionError
________________ test_lint_safe_warn_requires_force_then_allows ________________

    def test_lint_safe_warn_requires_force_then_allows() -> None:
        blocked = _run(["bash", "tools/ops/lint_safe.zsh", "--no-refresh"], force_level="WARN")
>       assert blocked.returncode == 41, blocked.stdout + blocked.stderr
E       AssertionError: safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json
E         
E       assert 43 == 41
E        +  where 43 = CompletedProcess(args=['bash', 'tools/ops/lint_safe.zsh', '--no-refresh'], returncode=43, stdout='', stderr='safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json\n').returncode

core/verify/test_phase10g_safe_wrappers.py:32: AssertionError
___________________________ test_healthy_state_noop ____________________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108857b60>
tmp_path = PosixPath('/private/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/pytest-of-icmini/pytest-166/test_healthy_state_noop0')

    def test_healthy_state_noop(monkeypatch, tmp_path: Path) -> None:
        runtime_root = tmp_path / "runtime"
        monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    
        def fake_run(args, cwd, capture_output, text, env, check):
            cmd = args[1:]
            if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
                return _cp(args, 0, {"overall_status": "HEALTHY"})
            if cmd == ["tools/ops/operator_status_report.py", "--json"]:
                return _cp(
                    args,
                    0,
                    {
                        "overall_status": "HEALTHY",
                        "api_server": "RUNNING",
                        "redis": "RUNNING",
                        "memory_status": "OK",
                    },
                )
            raise AssertionError(args)
    
        monkeypatch.setattr(subprocess, "run", fake_run)
    
        decisions = remediation_engine.run_once(runtime_root=runtime_root)
    
        assert len(decisions) == 1
>       assert decisions[0]["decision"] == "noop"
E       AssertionError: assert 'approval_missing' == 'noop'
E         
E         - noop
E         + approval_missing

core/verify/test_remediation_engine.py:43: AssertionError
_________________________ test_api_missing_no_approval _________________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1089ada20>

    def test_api_missing_no_approval(monkeypatch) -> None:
        decisions = remediation_engine.evaluate_remediation(
            {"overall_status": "FAILED"},
            {"overall_status": "CRITICAL", "api_server": "MISSING", "redis": "RUNNING", "memory_status": "OK"},
            timestamp="2026-03-08T00:00:00Z",
        )
    
        assert decisions[0]["decision"] == "approval_missing"
>       assert decisions[0]["target"] == "api"
E       AssertionError: assert 'bridge' == 'api'
E         
E         - api
E         + bridge

core/verify/test_remediation_engine.py:55: AssertionError
________________________ test_redis_missing_no_approval ________________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1089adbe0>

    def test_redis_missing_no_approval(monkeypatch) -> None:
        decisions = remediation_engine.evaluate_remediation(
            {"overall_status": "FAILED"},
            {"overall_status": "CRITICAL", "api_server": "RUNNING", "redis": "MISSING", "memory_status": "OK"},
            timestamp="2026-03-08T00:00:00Z",
        )
    
        assert decisions[0]["decision"] == "approval_missing"
>       assert decisions[0]["target"] == "redis"
E       AssertionError: assert 'bridge' == 'redis'
E         
E         - redis
E         + bridge

core/verify/test_remediation_engine.py:67: AssertionError
______________ test_memory_critical_manual_intervention_required _______________

    def test_memory_critical_manual_intervention_required() -> None:
        decisions = remediation_engine.evaluate_remediation(
            {"overall_status": "HEALTHY"},
            {"overall_status": "DEGRADED", "api_server": "RUNNING", "redis": "RUNNING", "memory_status": "CRITICAL"},
            timestamp="2026-03-08T00:00:00Z",
        )
    
>       assert len(decisions) == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = len([{'timestamp': '2026-03-08T00:00:00Z', 'decision': 'approval_missing', 'target': 'memory', 'reason': 'memory_status=CRITICAL; approval_missing:LUKA_ALLOW_MEMORY_RECOVERY', 'action_taken': False, 'source': 'remediation_engine'}, {'timestamp': '2026-03-08T00:00:00Z', 'decision': 'approval_missing', 'target': 'bridge', 'reason': 'bridge_status=UNAVAILABLE; bridge_consumer=missing_or_invalid; bridge_watchdog=missing_or_invalid; consumer=unavailable; inflight=unavailable; outbox=unavailable; approval_missing:LUKA_ALLOW_WORKER_RECOVERY', 'action_taken': False, 'source': 'remediation_engine'}])

core/verify/test_remediation_engine.py:77: AssertionError
___________________ test_configured_action_path_unavailable ____________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1088569e0>

    def test_configured_action_path_unavailable(monkeypatch) -> None:
        monkeypatch.setenv("LUKA_ALLOW_API_RESTART", "1")
        monkeypatch.setattr(remediation_engine, "API_RESTART_PATH", Path("/nonexistent/restart.zsh"))
    
        decisions = remediation_engine.evaluate_remediation(
            {"overall_status": "FAILED"},
            {"overall_status": "CRITICAL", "api_server": "MISSING", "redis": "RUNNING", "memory_status": "OK"},
            timestamp="2026-03-08T00:00:00Z",
        )
    
>       assert decisions[0]["decision"] == "action_unavailable"
E       AssertionError: assert 'approval_missing' == 'action_unavailable'
E         
E         - action_unavailable
E         + approval_missing

core/verify/test_remediation_engine.py:92: AssertionError
____________________ test_approved_api_restart_action_taken ____________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x108425be0>
tmp_path = PosixPath('/private/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/pytest-of-icmini/pytest-166/test_approved_api_restart_acti0')

    def test_approved_api_restart_action_taken(monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("LUKA_ALLOW_API_RESTART", "1")
        restart_path = tmp_path / "restart_api.zsh"
        restart_path.write_text("#!/bin/zsh\n", encoding="utf-8")
        monkeypatch.setattr(remediation_engine, "API_RESTART_PATH", restart_path)
    
        def fake_restart():
            return True, "api_restart_executed"
    
        monkeypatch.setattr(remediation_engine, "_run_api_restart", fake_restart)
    
        decisions = remediation_engine.evaluate_remediation(
            {"overall_status": "FAILED"},
            {"overall_status": "CRITICAL", "api_server": "MISSING", "redis": "RUNNING", "memory_status": "OK"},
            timestamp="2026-03-08T00:00:00Z",
        )
    
>       assert decisions[0]["decision"] == "restart_api"
E       AssertionError: assert 'approval_missing' == 'restart_api'
E         
E         - restart_api
E         + approval_missing

core/verify/test_remediation_engine.py:146: AssertionError
____________________________ test_lane_filter_works ____________________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1089ad010>

    def test_lane_filter_works(monkeypatch) -> None:
        client = TestClient(mission_control_server.app)
    
        def fake_load(lane=None, last=None):
            assert lane == "memory"
            return {"memory": {"attempts": 2, "lifecycle": ["approval_missing"]}, "last_event": {"decision": "approval_missing", "lane": "memory", "timestamp": "2026-03-08T00:00:00Z"}, "timeline": []}
    
        monkeypatch.setattr(mission_control_server, "load_remediation_history", fake_load)
    
>       response = client.get("/api/remediation_history?lane=memory")
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

core/verify/test_remediation_history_api.py:50: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/testclient.py:473: in get
    return super().get(
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:1053: in get
    return self.request(
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/testclient.py:445: in request
    return super().request(
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/icmini/Library/Python/3.14/lib/python/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/homebrew/Cellar/python@3.14/3.14.2_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/concurrent/futures/_base.py:450: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/opt/homebrew/Cellar/python@3.14/3.14.2_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/concurrent/futures/_base.py:395: in __get_result
    raise self._exception
/Users/icmini/Library/Python/3.14/lib/python/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/routing.py:78: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/Users/icmini/Library/Python/3.14/lib/python/site-packages/starlette/routing.py:75: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
interface/operator/mission_control_server.py:692: in remediation_history_endpoint
    payload.update(load_remediation_history(last=last))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

lane = None, last = 100

    def fake_load(lane=None, last=None):
>       assert lane == "memory"
E       AssertionError: assert None == 'memory'

core/verify/test_remediation_history_api.py:45: AssertionError
_______________ test_memory_failure_first_attempt_uses_priority ________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x1085617f0>
tmp_path = PosixPath('/private/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/pytest-of-icmini/pytest-166/test_memory_failure_first_atte0')

    def test_memory_failure_first_attempt_uses_priority(monkeypatch, tmp_path: Path) -> None:
        runtime_root = tmp_path / "runtime"
        monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
        monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
        monkeypatch.setattr(
            subprocess,
            "run",
            _fake_status_runner(
                {"overall_status": "HEALTHY"},
                {
                    "overall_status": "DEGRADED",
                    "memory_status": "CRITICAL",
                    "bridge_status": "FAILED",
                    "api_server": "RUNNING",
                    "redis": "RUNNING",
                    "details": {"bridge_checks": {"consumer": "stalled", "inflight": "failed", "outbox": "ok"}},
                    "errors": [],
                },
            ),
        )
        monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (True, "bridge_status=FAILED"))
        monkeypatch.setattr(
            memory_recovery,
            "evaluate_memory_recovery",
            lambda runtime_status, operator_status, timestamp=None, runtime_root=None: [
                {
                    "timestamp": timestamp,
                    "decision": "memory_recovery_started",
                    "target": "memory",
                    "reason": "started",
                    "action_taken": True,
                    "source": "remediation_engine",
                },
                {
                    "timestamp": timestamp,
                    "decision": "memory_recovery_finished",
                    "target": "memory",
                    "reason": "finished",
                    "action_taken": True,
                    "source": "remediation_engine",
                },
            ],
        )
        monkeypatch.setattr(worker_recovery, "evaluate_worker_recovery", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("worker lane should not run")))
    
        decisions = remediation_engine.run_once(runtime_root=runtime_root)
    
>       assert [item["decision"] for item in decisions] == ["memory_recovery_started", "memory_recovery_finished"]
E       AssertionError: assert ['memory_recovery_started', 'memory_recovery_finished', 'remediation_recovered'] == ['memory_recovery_started', 'memory_recovery_finished']
E         
E         Left contains one more item: 'remediation_recovered'
E         
E         Full diff:
E           [
E               'memory_recovery_started',
E               'memory_recovery_finished',
E         +     'remediation_recovered',
E           ]

core/verify/test_remediation_policy.py:106: AssertionError
______________________ test_retry_attempt_after_cooldown _______________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10852bcb0>
tmp_path = PosixPath('/private/var/folders/bm/8smk0tgn55q9zf1bh3l0n9zw0000gn/T/pytest-of-icmini/pytest-166/test_retry_attempt_after_coold0')

    def test_retry_attempt_after_cooldown(monkeypatch, tmp_path: Path) -> None:
        runtime_root = tmp_path / "runtime"
        state_dir = runtime_root / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "remediation_state.json").write_text(
            json.dumps(
                {
                    "memory_recovery_attempts": 1,
                    "worker_recovery_attempts": 0,
                    "memory_last_attempt": "2026-03-07T23:55:00Z",
                    "worker_last_attempt": None,
                    "last_attempt": "2026-03-07T23:55:00Z",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
        monkeypatch.setattr(remediation_engine, "_utc_now", lambda: "2026-03-08T00:00:00Z")
        monkeypatch.setattr(
            subprocess,
            "run",
            _fake_status_runner(
                {"overall_status": "HEALTHY"},
                {
                    "overall_status": "DEGRADED",
                    "memory_status": "CRITICAL",
                    "bridge_status": "OK",
                    "api_server": "RUNNING",
                    "redis": "RUNNING",
                    "details": {"bridge_checks": {"consumer": "idle", "inflight": "ok", "outbox": "ok"}},
                    "errors": [],
                },
            ),
        )
        monkeypatch.setattr(worker_recovery, "bridge_recovery_required", lambda operator_status: (False, "bridge_status=OK"))
        monkeypatch.setattr(
            memory_recovery,
            "evaluate_memory_recovery",
            lambda runtime_status, operator_status, timestamp=None, runtime_root=None: [
                {
                    "timestamp": timestamp,
                    "decision": "memory_recovery_started",
                    "target": "memory",
                    "reason": "started",
                    "action_taken": True,
                    "source": "remediation_engine",
                },
                {
                    "timestamp": timestamp,
                    "decision": "memory_recovery_finished",
                    "target": "memory",
                    "reason": "finished",
                    "action_taken": True,
                    "source": "remediation_engine",
                },
            ],
        )
    
        decisions = remediation_engine.run_once(runtime_root=runtime_root)
    
        assert decisions[0]["decision"] == "memory_recovery_started"
        state = json.loads((state_dir / "remediation_state.json").read_text(encoding="utf-8"))
>       assert state["memory_recovery_attempts"] == 2
E       assert 0 == 2

core/verify/test_remediation_policy.py:174: AssertionError
=========================== short test summary info ============================
FAILED core/verify/test_linguist_cli_v0.py::test_cli_happy_path_vector_001 - AssertionError: {"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_4b4bb99ffb76496b928c264006f3a495"}
  
assert 1 == 0
 +  where 1 = CompletedProcess(args=['python3', '-m', 'core.linguist_cli', '--input', "Create file notes/today.txt with text 'hello team'"], returncode=1, stdout='{"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_4b4bb99ffb76496b928c264006f3a495"}\n', stderr='').returncode
FAILED core/verify/test_linguist_cli_v0.py::test_cli_fail_closed_delete_all - AssertionError: {"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_18069d88e06640bfa1b1d8689f09c833"}
  
assert 1 == 2
 +  where 1 = CompletedProcess(args=['python3', '-m', 'core.linguist_cli', '--input', '\u0e25\u0e1a\u0e44\u0e1f\u0e25\u0e4c\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14\u0e43\u0e19\u0e42\u0e1b\u0e23\u0e40\u0e08\u0e01\u0e15\u0e4c'], returncode=1, stdout='{"ok": false, "error": "sentry_violation:activity_feed_missing", "trace": "trace_18069d88e06640bfa1b1d8689f09c833"}\n', stderr='').returncode
FAILED core/verify/test_phase10g_safe_wrappers.py::test_pytest_safe_warn_requires_force_then_allows - AssertionError: safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json
  
assert 43 == 41
 +  where 43 = CompletedProcess(args=['bash', 'tools/ops/pytest_safe.zsh', '--no-refresh'], returncode=43, stdout='', stderr='safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json\n').returncode
FAILED core/verify/test_phase10g_safe_wrappers.py::test_lint_safe_warn_requires_force_then_allows - AssertionError: safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json
  
assert 43 == 41
 +  where 43 = CompletedProcess(args=['bash', 'tools/ops/lint_safe.zsh', '--no-refresh'], returncode=43, stdout='', stderr='safe_run: telemetry_missing:/private/tmp/phase10_impl/observability/telemetry/ram_monitor.latest.json\n').returncode
FAILED core/verify/test_remediation_engine.py::test_healthy_state_noop - AssertionError: assert 'approval_missing' == 'noop'
  
  - noop
  + approval_missing
FAILED core/verify/test_remediation_engine.py::test_api_missing_no_approval - AssertionError: assert 'bridge' == 'api'
  
  - api
  + bridge
FAILED core/verify/test_remediation_engine.py::test_redis_missing_no_approval - AssertionError: assert 'bridge' == 'redis'
  
  - redis
  + bridge
FAILED core/verify/test_remediation_engine.py::test_memory_critical_manual_intervention_required - AssertionError: assert 2 == 1
 +  where 2 = len([{'timestamp': '2026-03-08T00:00:00Z', 'decision': 'approval_missing', 'target': 'memory', 'reason': 'memory_status=CRITICAL; approval_missing:LUKA_ALLOW_MEMORY_RECOVERY', 'action_taken': False, 'source': 'remediation_engine'}, {'timestamp': '2026-03-08T00:00:00Z', 'decision': 'approval_missing', 'target': 'bridge', 'reason': 'bridge_status=UNAVAILABLE; bridge_consumer=missing_or_invalid; bridge_watchdog=missing_or_invalid; consumer=unavailable; inflight=unavailable; outbox=unavailable; approval_missing:LUKA_ALLOW_WORKER_RECOVERY', 'action_taken': False, 'source': 'remediation_engine'}])
FAILED core/verify/test_remediation_engine.py::test_configured_action_path_unavailable - AssertionError: assert 'approval_missing' == 'action_unavailable'
  
  - action_unavailable
  + approval_missing
FAILED core/verify/test_remediation_engine.py::test_approved_api_restart_action_taken - AssertionError: assert 'approval_missing' == 'restart_api'
  
  - restart_api
  + approval_missing
FAILED core/verify/test_remediation_history_api.py::test_lane_filter_works - AssertionError: assert None == 'memory'
FAILED core/verify/test_remediation_policy.py::test_memory_failure_first_attempt_uses_priority - AssertionError: assert ['memory_recovery_started', 'memory_recovery_finished', 'remediation_recovered'] == ['memory_recovery_started', 'memory_recovery_finished']
  
  Left contains one more item: 'remediation_recovered'
  
  Full diff:
    [
        'memory_recovery_started',
        'memory_recovery_finished',
  +     'remediation_recovered',
    ]
FAILED core/verify/test_remediation_policy.py::test_retry_attempt_after_cooldown - assert 0 == 2
======================= 13 failed, 447 passed in 19.15s ========================
- 0luka V.2 Health Check
========================================
Dispatcher:   watching (pid 71692, 56554 cycles, uptime 244697.9s)
Last dispatch: phase8_evidence_004 -> committed (2026-03-08T08:13:16Z)

Inbox:        0 pending
Completed:    0 tasks
Rejected:     0 tasks
Outbox:       0 results

Schemas:      6 registered (dispatch_latest, envelope, evidence_min, router_audit, run_result, task)

Tests:        21/21 passed
  [pass] test_ref_resolver.py
  [pass] test_phase1c_gate.py
  [pass] test_phase1d_result_gate.py
  [pass] test_phase1e_outbox_writer.py
  [pass] test_phase1e_no_hardpath_in_result.py
  [pass] test_clec_gate.py
  [pass] test_e2e_clec_pipeline.py
  [pass] test_task_dispatcher.py
  [pass] test_submit.py
  [pass] test_health.py
  [pass] test_smoke.py
  [pass] test_ledger.py
  [pass] test_retention.py
  [pass] test_config.py
  [pass] test_cli.py
  [pass] test_bridge.py
  [pass] test_timeline.py
  [pass] test_seal.py
  [pass] test_circuit_breaker.py
  [pass] test_watchdog.py
  [pass] test_pack10_index_sovereignty.py

Status: HEALTHY

## Runtime File Hashes (SHA256)
- activity_feed.jsonl: b8f95b5c10e458f74a6dec9f73a8cf6eac45ef6dfe3c3845bd7486f079ffb436
- remediation_history.jsonl: missing
- approval_log source (approval_actions.jsonl): 1636833567c73bf18269ce16f8647256a798781ce34ccb6956915639decaf0c8

## Git Commit
- 1b9cb209224396b33d8f4eb4881f1bba1b90ce80
