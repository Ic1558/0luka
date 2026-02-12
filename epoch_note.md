# Epoch Note (use only if recovery is impossible)

Status: **Template prepared** (not activated).

When to activate:
- No usable ancestor commits can be proven from `.git/objects` + `git fsck`.
- Recovered commit set is insufficient for provenance requirements.

Declaration text (fill values before commit):

> We declare a new provenance epoch at commit `<NEW_EPOCH_COMMIT>` on `<UTC_TIMESTAMP>`.
> Prior history is considered **truncated/unrecoverable** from local evidence.
> Forensic snapshot artifacts are preserved at `<RECOVERY_DIR>` with checksum manifest `<CHECKSUM_FILE>`.
> This declaration is fail-closed: no destructive history rewrite was performed.

Required attachments:
- recovery_report.md
- object_inventory.txt
- snapshot_checksums.txt
- gitdir backup archive (`gitdir_backup.tgz`)
