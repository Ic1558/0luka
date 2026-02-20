# System Next Move Plan (Enterprise Grade, Plan-Only, Fail-Closed)

## 1) Executive intent
Stabilize provenance and operational trust using a fail-closed workflow, then decide between **Recoverable** and **Declare New Epoch** without mutating kernel/runtime code paths.

## 2) Trigger / Why this plan exists
- Previous automated changes were unsatisfactory and evidence confidence must be re-established.
- Repo-level anomalies (locks/FETCH_HEAD/permission instability) can invalidate normal mutate-first workflows.
- Governance requires deterministic, auditable recovery gates before execution.

## 3) No-mutation boundary (hard scope lock)
Allowed in this plan stage:
- `system_next_move_plan.md`
- `recovery_report.md`
- `object_inventory.txt`
- `epoch_note.md`

Forbidden in this plan stage:
- `core/`, `core_brain/`, `tools/`, `.github/`
- `governance_lock_manifest.json`, `phase_status.yaml`
- Any runtime/kernel/config mutation outside the 4 plan artifacts

## 4) Enterprise Audit Checklist (must-pass)

### A. Scope / Safety (precondition)
- Docs-only changes in the 4 plan artifacts.
- No touch outside plan scope boundary.
- No governance lock/phase file mutation.
- `git status --short` is clean after commit.
- `git diff --name-only HEAD~1..HEAD` returns only plan artifacts.

### B. Evidence (must exist in report)
- Commit SHA + UTC timestamp.
- Trigger statement (why recovery plan was required).
- Explicit no-mutation boundary.
- Decision gate checkpoint (where to stop for approval).
- Rollback strategy even for plan-only stage.

### C. Operational Readiness (must execute)
- Phases: **Contain / Verify / Decide / Execute**.
- RACI owner for each phase.
- Stop conditions (if X then halt).
- Proof commands that emit reproducible evidence.

## 5) Decision Gate Matrix (Recoverable vs Declare New Epoch)
| Check | Recoverable (go) | Declare New Epoch (stop + replace baseline) |
|---|---|---|
| Git repo writable | `.git` writable; no EPERM | EPERM persists / mount policy anomaly / TCC block |
| FETCH/LOCK errors | Resolved via auditable fix | Recurs, non-deterministic |
| Working tree integrity | Clean and fully restorable | Tracked files drift/loss without root cause |
| Remote trust | Fetch/push stable | Remote operations fail-closed repeatedly |
| Evidence continuity | Report dir + checksums complete | Evidence missing/inconsistent |
| Blast radius | Limited to docs plan | Requires core/governance/runtime mutation |
| Time cost | <= 1 layer remediation | >= 2 layers remediation |

**Fail-closed rule:** If any `Declare New Epoch` condition is repeatably true, halt at **Decide** and open new epoch.

## 6) Phase model with owners, stop conditions, proof

### Phase 0 — Contain
- Owner: Incident Lead + Git Forensics
- Action: freeze refs policy, capture forensic snapshot/checksum
- Stop: snapshot cannot be created or checksum mismatch
- Proof commands:
  - `git status --porcelain=v2 --branch`
  - `tar -czf reports/recovery_<ts>/gitdir_backup.tgz .git`
  - `sha256sum reports/recovery_<ts>/gitdir_backup.tgz`

### Phase 1 — Verify
- Owner: Git Forensics (R), Governance (C)
- Action: collect commit/object/reflog evidence, test determinism
- Stop: fsck corruption, non-reproducible lock/fetch behavior
- Proof commands:
  - `git fsck --full --no-reflogs --unreachable --lost-found`
  - `git rev-list --all --date-order | wc -l`
  - `git reflog --date=iso | head -n 50`

### Phase 2 — Decide (mandatory gate)
- Owner: Governance Reviewer (A)
- Action: apply gate matrix and sign decision record
- Stop: no dual sign-off (Engineering + Governance)
- Proof artifacts:
  - signed decision record (`recoverable`/`new-epoch`)
  - matrix evaluation attached to report

### Phase 3 — Execute
- Owner: Runtime Lead + Incident Lead
- Path A (recoverable): create rescue refs, reconcile branches
- Path B (new epoch): epoch declaration commit + baseline tags
- Stop: any action crossing no-mutation boundary without approved change request

## 7) RACI
- Incident Lead — **Owner** timeline and final closure
- Git Forensics — **Responsible** for technical evidence and confidence score
- Governance Reviewer — **Approver** for gate decision
- Runtime Lead — **Consulted** for execution safety/rollback
- Stakeholders — **Informed** via daily RAG status

## 8) Rollback strategy (plan-only stage)
- Keep immutable `.git` archive + checksum manifest prior to any execution mutation.
- If verification fails, revert to evidence snapshot state and remain in gate-hold mode.
- No force-push/history rewrite allowed during gate-hold.

## 9) Definition of Done
1. Decision record signed (`recoverable` or `new-epoch`).
2. Forensic bundle checksums verified.
3. Commit/object inventory accepted by Governance.
4. Scope/safety audit checklist passes.
5. Post-incident prevention actions assigned with owners/dates.
