# AG-34 — Supervised Drift Repair Execution

**System:** Supervised Agentic Runtime Platform
**Snapshot:** 2026-03-16 (post AG-33)
**Status:** Phase Definition + Implementation Spec

---

## 1. Objective

AG-34 is the first execution bridge between governance-approved repair intent and real system mutation.

The full detection-to-resolution pipeline is:

```
AG-31: detect drift
AG-32: govern finding lifecycle
AG-33: plan repair (operator review)
AG-34: operator approve → execute repair under constraints → verify
```

AG-34 is NOT autonomous self-healing.
AG-34 is supervised repair execution only.
It may execute only operator-approved repair plans.
It must never execute unapproved plans, never bypass operator governance, and never mutate outside the approved repair scope.

After AG-34, the system classification becomes:

> **Self-auditing runtime with governed drift review, structured repair planning, and supervised repair execution**

It is NOT yet: autonomous self-healing architecture.

---

## 2. Scope

### AG-34 MUST support

- Reading only operator-approved AG-33 repair plans
- Executing repair within an explicit allowed file scope
- Generating repair execution evidence (before/after state)
- Preserving pre/post state proof (hashes, timestamps)
- Re-running verification after repair
- Updating repair execution outcome
- Handing result back to AG-31/AG-32 for re-audit / lifecycle continuation

### AG-34 MUST NOT

- Auto-approve plans
- Auto-select plans without governance state
- Execute non-approved repair plans
- Repair outside declared `target_files`
- Close findings by itself unless explicitly allowed by governance contract
- Modify `audit_baseline.py` automatically
- Run destructive governance actions without `operator_id`
- Bypass CLEC pre-claim gates
- Bypass root allowlist
- Bypass secrets policy

---

## 3. Inputs

AG-34 consumes:

| Input | Source |
|---|---|
| `drift_repair_plans.jsonl` | AG-33 output (append-only) |
| `drift_finding_status.json` | AG-32 governance state |
| Approved repair decision metadata | operator-submitted via API |
| Canonical architecture truth layer | `g/reports/architecture/0luka_architecture_diagram_ag30.md` |
| Runtime capability matrix | `g/reports/architecture/0luka_runtime_capability_matrix.md` |
| Mission Control route layer | `interface/operator/mission_control_server.py` |
| Operator approval metadata | `operator_id`, `approved_at`, `approved_target_files`, `approved_action_scope` |

---

## 4. Approval Model

### Repair plan lifecycle states

| State | Definition |
|---|---|
| `PROPOSED` | AG-33 generated the plan; no operator action yet |
| `APPROVED` | Operator explicitly approved the plan for execution with full metadata |
| `EXECUTED` | AG-34 ran the bounded repair; outcome recorded |
| `VERIFIED` | Post-repair verification passed |
| `FAILED` | Execution or verification failed |
| `REVERTED` | Operator explicitly reverted the repair (manual rollback) |

### Minimum approved plan contract

A plan is executable by AG-34 only if it has ALL of:

```json
{
  "plan_id": "<non-empty>",
  "finding_id": "<non-empty>",
  "operator_id": "<non-empty>",
  "approved_at": "<ISO timestamp>",
  "approved_target_files": ["<file1>", ...],
  "approved_action_scope": "<description of allowed actions>",
  "status": "APPROVED"
}
```

If any field is missing → `validate_execution_scope()` returns `BLOCK`.

### Transition rules

```
PROPOSED  →  APPROVED    (operator approves via POST /run with approval metadata)
APPROVED  →  EXECUTED    (AG-34 runs bounded repair)
EXECUTED  →  VERIFIED    (post-repair verification PASSED)
EXECUTED  →  FAILED      (post-repair verification FAILED or execution error)
FAILED    →  APPROVED    (operator re-approves for retry)
EXECUTED  →  REVERTED    (operator explicitly reverts)
VERIFIED  →  REVERTED    (operator explicitly reverts even after verification)
```

AG-34 does NOT own `RESOLVED` — that is AG-32's domain.

---

## 5. Execution Boundary

AG-34 enforces the following hard safety boundary:

### Hard stops (immediate BLOCK)

| Rule | Details |
|---|---|
| Only approved `target_files` may be touched | Files not in `approved_target_files` → BLOCK |
| No wildcard repair scope | Glob patterns, `*`, `/` → BLOCK |
| No root-level structural mutation outside PRPS | Cannot delete kernel dirs, core/ layout, etc. |
| No bypass of CLEC pre-claim gates | All write ops go through CLEC contract |
| No bypass of root allowlist | `/Users/` hardcoded paths rejected |
| No bypass of secrets policy | `.env`, `id_rsa*`, `*.pem` patterns → BLOCK |
| No bypass of operator gate | All POST endpoints require `operator_id` |
| Evidence-first | No execution without pre-state snapshot |

### Scope validation verdicts

| Verdict | Meaning |
|---|---|
| `ALLOW` | All checks pass, execution may proceed |
| `BLOCK` | Hard constraint violated; execution stops |
| `ESCALATE` | Ambiguous scope; requires operator re-confirmation |

---

## 6. Proposed Implementation Surface

Minimal surface only:

```
core/audit/repair_execution_store.py          — append-only log + atomic latest
core/audit/drift_repair_executor.py           — execution orchestrator
interface/operator/api_drift_repair_execution.py  — Mission Control surface
core/verify/test_ag34_supervised_repair_execution.py  — test suite
```

Patch:

```
interface/operator/mission_control_server.py  — AG-34 route block (graceful fallback)
```

---

## 7. Runtime Outputs

| File | Type | Purpose |
|---|---|---|
| `$LUKA_RUNTIME_ROOT/state/drift_repair_execution_log.jsonl` | append-only JSONL | One record per execution |
| `$LUKA_RUNTIME_ROOT/state/drift_repair_execution_latest.json` | atomic overwrite | Latest execution summary |

Every execution record must contain:

```json
{
  "ts": "2026-03-16T...",
  "execution_id": "repair-exec-<hex>",
  "finding_id": "...",
  "plan_id": "...",
  "operator_id": "...",
  "target_files": ["..."],
  "before_state": [{"path": "...", "sha256_before": "...", "exists_before": true, "mtime_before": 0}],
  "after_state": [{"path": "...", "sha256_after": "...", "exists_after": true, "mtime_after": 0}],
  "executed_actions": ["..."],
  "verification_status": "PASSED | FAILED | INCONCLUSIVE",
  "status": "EXECUTED | FAILED",
  "operator_approval_ref": "..."
}
```

---

## 8. Verification Model

### Verification pipeline

```
1. pre-repair snapshot   → sha256 + mtime per target file
2. bounded execution     → apply approved actions only
3. post-repair snapshot  → sha256 + mtime per target file
4. comparison            → before != after confirms mutation; hash logged
5. verification          → import check / syntax check / targeted test run
6. regression check      → optional AG-31 re-audit trigger proposal
```

### Verification verdicts

| Verdict | Meaning |
|---|---|
| `PASSED` | File changed as expected, verification checks pass |
| `FAILED` | Verification checks failed; repair may have introduced regression |
| `INCONCLUSIVE` | Cannot determine — file state ambiguous or check unavailable |

### Critical distinction

```
repair executed  ≠  repair proven
```

A repair becomes trustworthy only after `verification_status == PASSED`.
`EXECUTED` status alone does not imply correctness.

---

## 9. Governance Interactions

AG-34 participates in the AG-32 lifecycle but does NOT own it.

### Correct flow

```
AG-32: ESCALATED finding
→ AG-33: generate PROPOSED repair plan
→ Operator: approve plan (status → APPROVED)
→ AG-34: execute bounded repair → EXECUTED
→ AG-34: run verification → verification_status
→ AG-34: write execution record
→ AG-32: operator reviews result → RESOLVED | ESCALATED_AGAIN | OPEN
```

### AG-34 may NOT

- Set finding status to `RESOLVED` directly
- Close the governance lifecycle
- Modify `drift_finding_status.json` — that is AG-32's responsibility

### AG-34 SHOULD

- Return execution result and `verification_status` via API
- Allow operator to feed the result back to AG-32 via `POST /api/drift_governance/resolve`

---

## 10. Mission Control Integration

AG-34 exposes the following operator-facing surfaces:

| Surface | Endpoint | Auth |
|---|---|---|
| Repair execution history | `GET /api/drift_repair_execution/history` | none |
| Latest execution summary | `GET /api/drift_repair_execution/latest` | none |
| Single execution record | `GET /api/drift_repair_execution/{execution_id}` | none |
| Run approved repair | `POST /api/drift_repair_execution/run` | `operator_id` required |
| Re-run verification | `POST /api/drift_repair_execution/verify` | `operator_id` required |

---

## 11. Safety Constraints

These invariants from the canonical architecture MUST be preserved:

| Rule | Constraint |
|---|---|
| Operator remains final authority | No execution without operator_id |
| No auto-rollback policy | Rollback requires explicit operator action |
| All destructive actions require operator_id | POST /run + POST /verify both 403 without it |
| Kernel remains deterministic | No free-form code mutation; bounded action list only |
| AG-34 is supervised mutation, not self-governance | Findings resolved by AG-32, not AG-34 |

---

## 12. Final Deliverables

### A. This document — `ag34_supervised_repair_execution.md`

### B. Executive verdict — why AG-34 is the correct next phase

The audit/governance/planning stack (AG-31/32/33) can detect and articulate drift with precision. Without AG-34, all repair intelligence stops at the planning stage — a human must manually implement every plan. AG-34 closes the loop in a bounded, supervised way: it executes only what the operator has explicitly approved, only within the declared file scope, and produces full before/after evidence so every repair can be audited and reversed. This is the minimum viable execution bridge that respects the governance boundary while eliminating manual implementation burden for operator-approved repairs.

### C. Top 5 execution risks AG-34 must guard against first

| # | Risk | Guard |
|---|---|---|
| 1 | Execution of non-approved plan | `validate_execution_scope()` checks `status == APPROVED` before any mutation |
| 2 | Scope creep — touching files outside `target_files` | Hard BLOCK if target not in `approved_target_files` |
| 3 | No evidence left behind | `capture_pre_repair_state()` must succeed before `execute_repair_plan()` is called |
| 4 | Verification bypass — marking repair as verified without running checks | `verification_status` is always set; default is `INCONCLUSIVE`, not `PASSED` |
| 5 | Auto-closing findings — AG-34 silently marking finding RESOLVED | AG-34 writes execution records only; finding lifecycle owned exclusively by AG-32 |

### D. Repair plan state taxonomy

| State | Who sets it | Meaning |
|---|---|---|
| `PROPOSED` | AG-33 (planning engine) | Plan exists, not yet reviewed by operator |
| `APPROVED` | Operator (via API / explicit metadata) | Operator has reviewed and authorised execution |
| `EXECUTED` | AG-34 (repair executor) | Bounded repair ran; outcome and evidence recorded |
| `VERIFIED` | AG-34 (post-repair verification) | Execution passed all post-repair checks |
| `FAILED` | AG-34 (execution or verification failure) | Something went wrong; operator review required |
| `REVERTED` | Operator (explicit rollback action) | Repair was undone; system returned to prior state |

---

## Architecture Position

```
L11 [AG-31: Runtime Self-Audit]
     ↓ drift findings
L12 [AG-32: Drift Governance]
     ↓ ESCALATED findings
L13 [AG-33: Repair Planning]
     ↓ PROPOSED repair plans
     ↓ operator approval
L14 [AG-34: Supervised Repair Execution]   ← this phase
     ↓ EXECUTED + verification_status
     ↑ result handed back to AG-32 for final lifecycle closure
```

AG-34 is a supervised mutation layer. It is the last layer before the operator makes the final governance call in AG-32.
