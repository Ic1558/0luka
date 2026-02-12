# Epoch Note (Activate only when recovery is not trustworthy)

Status: **Template prepared** (not activated).

## Activation criteria (fail-closed)
Activate this declaration when one or more conditions are repeatably true:
- `.git` remains non-writable (EPERM / mount/TCC anomaly).
- FETCH/LOCK failures are non-deterministic after auditable remediation.
- Tracked working tree integrity cannot be restored with known cause.
- Evidence continuity is broken (missing/inconsistent checksums or artifacts).
- Required fix crosses no-mutation boundary (core/governance/runtime).

## Declaration template (fill before commit)

> We declare a new provenance epoch at commit `<NEW_EPOCH_COMMIT>` on `<UTC_TIMESTAMP>`.
> Prior history is treated as **truncated/unrecoverable** based on local evidence quality.
> Recovery evidence is preserved at `<RECOVERY_DIR>` with checksum manifest `<CHECKSUM_FILE>`.
> Decision gate result: `<DECISION_RECORD_ID>` approved by `<ENGINEERING_APPROVER>` and `<GOVERNANCE_APPROVER>`.
> This action is fail-closed and avoids destructive history rewrite.

## Required attachments
- `recovery_report.md`
- `system_next_move_plan.md`
- `object_inventory.txt`
- `reports/recovery_<ts>/snapshot_checksums.txt`
- `reports/recovery_<ts>/gitdir_backup.tgz`
- Signed decision record (`recoverable` / `new-epoch`)
