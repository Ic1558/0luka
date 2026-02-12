# Governance Escalation Matrix (Step 5 Draft)

## Violation Types
- `registry_mismatch`
- `synthetic_proof_detected`
- `missing_artifact`
- `dirty_worktree_proof`
- `hash_tampering`

## Escalation Levels
| Level | Action | CI Behavior | Required Response |
|---|---|---|---|
| L1 | Warn | Non-blocking warning | Add issue and remediation owner |
| L2 | Block PR | Required check fails | Fix before merge |
| L3 | Require epoch declaration | Required check fails + governance approval gate | Add `epoch_note.md` and forensic references |
| L4 | Freeze repo | Block all non-governance merges | Manual sovereign approval to unfreeze |

## Signal Sources (to bind after Step 4)
- Step 2 lock guard output (`governance_file_lock.py`)
- Step 3 growth guard output (`phase_growth_guard.py`)
- Step 4 cross-repo aggregator conflict signals
- DoD checker proof mode and artifact integrity signals

## CI Binding Plan
- Map each violation type to one escalation level in workflow policy config.
- Emit deterministic JSON evidence on every failure.
- Keep policy fail-closed by default.
