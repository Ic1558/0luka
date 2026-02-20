# Git Repository Recovery Report (Fail-Closed, Plan-Only)

## A) Diagnosis (short)

Local history is partially observable through refs/objects while reflog depth is shallow; therefore provenance confidence is insufficient for mutate-first recovery. This plan enforces docs-only controls, deterministic evidence capture, and a mandatory decision gate before any execution mutations.

## B) Executive Summary (1-page)

**Title:** Git Repository Recovery — Plan-Only (Fail-Closed)

**Situation**

- Repo/refs anomalies (lock/FETCH_HEAD/permission instability) can compromise trust in normal mutation workflows.
- Prior auto-generated change quality was unsatisfactory, requiring governance-grade reset of decision flow.

**Objective**

- Constrain blast radius to docs only.
- Build an auditable decision gate (Recoverable vs New Epoch).
- Preserve evidence continuity with reproducible proofs.

**What changed (plan-only)**

- `system_next_move_plan.md` (control model + gate matrix + RACI + DoD)
- `epoch_note.md` (epoch declaration template + gate trigger)
- `object_inventory.txt` (evidence index + continuity pointers)
- `recovery_report.md` (this report)

**Controls**

- No kernel/runtime mutation
- No governance weakening
- No lock/phase status mutation
- Evidence append-only, checksum-verified

**Decision Gate**

- Stop after **Phase 0–1**.
- Governance approves `recoverable` vs `new-epoch` before execution.

**Next steps**

1. Contain: snapshot + checksum.
2. Verify: reproduce issue deterministically.
3. Decide: apply matrix and sign decision.
4. Execute: only after gate approval and proof completeness.

## C) Enterprise Audit Checklist Mapping

### Scope / Safety

- Docs-only plan artifacts: yes.
- No mutation in `core/`, `core_brain/`, `tools/`, `.github/`: required.
- No mutation in `governance_lock_manifest.json`, `phase_status.yaml`: required.

### Evidence

- Must record: commit SHA + UTC time, trigger, no-mutation boundary, decision gate checkpoint, rollback strategy.

### Operational readiness

- Must include: phased model, owners, stop conditions, proof commands.

## D) Decision Gate Matrix (execution criteria)

If any `Declare New Epoch` signal is repeatable, halt at **Decide** and do not execute mutation on old baseline.

## E) Safe proof commands (read-only first)

```bash
git log -1 --pretty=format:'%H %cI %s'
git show --name-only --pretty='' HEAD
git show --stat --oneline HEAD
git status --short
git diff --name-only HEAD~1..HEAD
```

Expected:

- Single commit metadata visible (SHA + timestamp).
- Changed files limited to 4 plan artifacts.
- Working tree clean after commit.

## F) Forensic review command block (copy/paste)

```bash
cd /workspace/0luka || exit 1
set -euo pipefail

echo "== COMMIT =="
git log -1 --oneline

echo "== CHANGED FILES (HEAD) =="
git show --name-only --pretty="" HEAD

echo "== DIFFSTAT =="
git show --stat --oneline HEAD

echo "== FILE HEADERS (first 60 lines each) =="
for f in system_next_move_plan.md epoch_note.md object_inventory.txt recovery_report.md; do
  echo "----- $f -----"
  test -f "$f" && sed -n '1,60p' "$f" || echo "MISSING: $f"
done
```

## G) Required evidence artifacts (DoD)

- `recovery_report.md`
- `system_next_move_plan.md`
- `object_inventory.txt`
- `epoch_note.md`
- `reports/recovery_<ts>/snapshot_checksums.txt`
- Signed decision record (`recoverable`/`new-epoch`)
