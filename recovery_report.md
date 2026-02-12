# Repository Recovery Report (Fail-Closed)

## A) Diagnosis (short)
Local repository has **no configured remote**, reflog depth is shallow for recent checkout/branch-renaming events, but object database still contains a substantial reachable commit graph (reachable commits: 234) and no dangling commits were found by fsck. This indicates history is not fully lost locally, though reflog evidence is truncated and cannot alone represent older lineage.

## B) Recovery plan

### Path 1: Recoverable (recommended for current state)
1. Freeze evidence: keep forensic snapshot under `reports/recovery_20260212T094141Z`.
2. Build authoritative commit map from reachable refs + object inventory:
   - `reports/recovery_20260212T094141Z/rev_list_all.txt`
   - `reports/recovery_20260212T094141Z/commit_inventory.txt`
3. Create protection refs for important tips **without rewriting**:
   - `git branch rescue/<name> <commit>`
4. Verify integrity after each step:
   - `git fsck --full --no-reflogs --unreachable --lost-found`
5. Export evidence bundle (tar + checksums) before any risky operation.

### Path 2: Not recoverable (declare new epoch)
1. Preserve all existing artifacts and checksums.
2. Commit `reports/recovery_report.md` + `reports/object_inventory.txt` + `reports/epoch_note.md`.
3. Create a provenance note (`reports/epoch_note.md`) declaring history truncation and linking forensic bundle.
4. Continue development only from new epoch commit; never claim continuity beyond proven commits.

## C) Safe command blocks (read-only first, then backup)

### 1) Read-only triage
```bash
git status --porcelain=v2 --branch
git remote -v
git reflog --date=iso | head -n 20
git branch -avv
git count-objects -v
git fsck --full --no-reflogs --unreachable --lost-found
git rev-list --all --date-order | wc -l
```
Expected validation:
- `git remote -v` is empty (no remote provenance).
- `git reflog` may show only recent events.
- `git fsck` reports no fatal corruption.
- reachable commit count > 0 indicates local history still exists.

### 2) Forensic backup (non-destructive)
```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "reports/recovery_${ts}"
git status --porcelain=v2 --branch > "reports/recovery_${ts}/git_status.txt"
git reflog --date=iso > "reports/recovery_${ts}/git_reflog.txt"
tar -czf "reports/recovery_${ts}/gitdir_backup.tgz" .git
sha256sum "reports/recovery_${ts}/gitdir_backup.tgz" > "reports/recovery_${ts}/snapshot_checksums.txt"
```
Expected validation:
- backup archive exists and checksum file contains one SHA-256 line.

### 3) Object + commit inventory
```bash
git rev-list --all --date-order > "reports/recovery_${ts}/rev_list_all.txt"
git fsck --full --no-reflogs --unreachable --lost-found > "reports/recovery_${ts}/fsck_unreachable.txt" 2>&1
awk '/dangling commit/{print $3}' "reports/recovery_${ts}/fsck_unreachable.txt" > "reports/recovery_${ts}/dangling_commit_ids.txt"
```
Expected validation:
- `rev_list_all.txt` non-empty when history is recoverable.
- dangling commit list may be empty; non-empty means potential extra recoverable commits.

## D) Required evidence artifacts
- `reports/recovery_report.md`
- `reports/object_inventory.txt`
- `reports/epoch_note.md`
- `reports/recovery_20260212T094141Z/snapshot_checksums.txt`
- `reports/recovery_20260212T094141Z/commit_inventory.txt`
