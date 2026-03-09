# HY-001 Stray Asset Classification

HEAD: `0ffaae8`  
Branch: `codex/phase3-8-proof-consumption-ux`

Input evidence: `.tmp_hy001_git_status.txt`

This is a classification-only report. It does **not** move/delete/ignore/commit anything.

## TRACK

Platform assets that likely belong in the repo (but may require review for naming/owner/doc links).

- `core/governance/auto_governor_contract.yaml` (modified; working control doc, likely track but defer seal/commit decision)
- `docs/governance/ESCALATION_MATRIX_DRAFT.md` (modified; governance doc, likely track but defer seal/commit decision)
- `docs/review/pre_commit_checks.md` (modified; developer workflow doc, likely track but defer seal/commit decision)
- `implementation_plan.md` (modified; working doc, likely track but defer seal/commit decision)
- `prps/core_architecture.md` (modified; architecture PRP, likely track but defer seal/commit decision)
- `task.md` (modified; working doc, likely track but defer seal/commit decision)
- `core_brain/governance/LIBRARIAN_POLICY.md` (untracked; appears to be new canonical policy under `core_brain/`)
- `tools/git/setup_git_hooks.zsh` (untracked; repo bootstrap tooling)
- `tools/bootstrap/` (untracked; repo bootstrap tooling directory)
- `system/launchd/install_mls_symlink_guard_launchagent.zsh` (untracked; deployment/ops)
- `system/launchd/phase_o_next.zsh` (untracked; deployment/ops)
- `system/launchd/rebootstrap_daily_summary.zsh` (untracked; deployment/ops)
- `system/launchd/setup_htmlhub_launchagent.zsh` (untracked; deployment/ops)
- `system/launchd/setup_lac_metrics_exporter_daily.zsh` (untracked; deployment/ops)

## MOVE

Misplaced docs/spec/plans that should live under `docs/` with an explicit structure.

- `archive/` -> propose `docs/archive/` (or `docs/review/archive/` depending on policy)
- `plans/root_strategy/` -> propose `docs/plans/root_strategy/`
- `spec/opal_lane_spec.md` -> propose `docs/spec/opal_lane_spec.md`
- `spec/studio_lane_spec.md` -> propose `docs/spec/studio_lane_spec.md`

## IGNORE

Assets that should remain outside git tracking (or be explicitly ignored), typically because they are repo topology artifacts or generated/local.

- `repos/qs/` (nested git repo directory; outer repo should not track it; ignore at outer level)

## LOCAL_ONLY

Machine/operator-specific or one-off recovery scripts that should not be tracked without an explicit promotion process (owner, naming, tests, runbook entry).

- `system/tools/ops/gg_autofix_after_reboot.zsh`
- `system/tools/ops/guard_antigravity.zsh`
- `system/tools/ops/panic_freeze_fix.zsh`
- `system/tools/ops/stop_antigravity_leaks.zsh`
- `tools/ops/clc_path_audit_fix.zsh`
- `tools/ops/gg_scan_safe_check.zsh`
- `tools/ops/gm_fix_zones_and_quicktest.zsh`
- `tools/ops/librarian_scaffold_v1.zsh`
- `tools/ops/ops_health.zsh`
- `tools/ops/phase_o_fix_current_logs.zsh`
- `tools/ops/promote.zsh`
- `tools/ops/scan_dupes_gd_vs_sot_FINAL.zsh`
- `tools/ops/scan_pending_no_result.zsh`
- `tools/ops/summarize_patches_exact_snippets.zsh`
- `tools/ops/telemetry_probe.zsh`
- `tools/ops/tk_guard_verify.zsh`
- `tools/ops/verify_ops_public.zsh`

