# AG-35 — Repair Verification & Governance Reconciliation

**System:** Supervised Agentic Runtime Platform
**Snapshot:** 2026-03-16 (post AG-34)
**Status:** Phase Definition + Implementation Spec

---

## 1. Objective

AG-35 determines whether an executed repair truly resolved the original drift and reconciles governance accordingly.

The complete pipeline is:

```
AG-31: detect drift
AG-32: govern finding lifecycle
AG-33: plan repair (operator review)
AG-34: execute approved repair (bounded, supervised)
AG-35: verify outcome + reconcile governance  ← this phase
AG-32: final lifecycle decision (operator authority)
```

AG-35 is NOT autonomous self-healing.
AG-35 NEVER closes findings, promotes baselines, or executes additional repairs.
AG-35 produces verification evidence and governance recommendations only.
Final lifecycle closure stays with AG-32 under operator authority.

---

## 2. Scope

### AG-35 MUST support

- Reading AG-34 repair execution results
- Performing bounded post-repair verification
- Optionally triggering targeted AG-31 re-audit (bounded, not full system scan)
- Comparing pre/post drift state to detect drift cleared / persists / regressed
- Generating reconciliation verdicts with evidence
- Emitting reconciliation artifacts (append-only log + atomic latest)
- Providing governance recommendations (recommend only — not apply)
- Exposing recommendations via Mission Control for operator decision

### AG-35 MUST NOT

- Execute repairs
- Modify `audit_baseline.py` automatically
- Close findings automatically
- Mutate `drift_finding_status.json` directly
- Re-run the full AG-31 system-wide audit (bounded targeted checks only)
- Auto-approve, auto-rollback, or auto-promote anything

---

## 3. Inputs

| Input | Source |
|---|---|
| `drift_repair_execution_log.jsonl` | AG-34 execution store |
| `drift_repair_execution_latest.json` | AG-34 latest summary |
| `drift_finding_status.json` | AG-32 governance state |
| `runtime_self_audit.json` | AG-31 latest audit |
| `drift_findings.jsonl` | AG-31 finding evidence |
| Runtime capability matrix | `g/reports/architecture/0luka_runtime_capability_matrix.md` |
| Canonical architecture SOT | `g/reports/architecture/0luka_architecture_diagram_ag30.md` |

---

## 4. Verification Model

AG-35 verifies repairs using evidence-first logic only.

### Minimum verification steps

1. Read repair execution record from AG-34 log
2. Validate `before_state` / `after_state` file snapshots (sha256 comparison)
3. Confirm repair stayed within approved `target_files`
4. Evaluate whether `executed_actions` match approved plan
5. Compare expected outcome vs observed outcome

### Verification verdicts

| Verdict | Meaning |
|---|---|
| `PASSED` | Evidence confirms repair applied correctly within scope |
| `FAILED` | Evidence shows repair did not apply or caused regression |
| `INCONCLUSIVE` | Evidence insufficient to determine outcome |

### Critical rule

```
repair executed  ≠  repair proven
```

`EXECUTED` status from AG-34 does not imply the drift was resolved.
AG-35 is the layer that makes that determination.

---

## 5. Drift Re-Audit

AG-35 may optionally perform a bounded targeted re-check (not a full AG-31 scan) to confirm whether the original drift condition still exists.

### Re-audit outcomes

| Outcome | Meaning |
|---|---|
| `DRIFT_CLEARED` | Original drift condition no longer detected |
| `DRIFT_PERSISTS` | Original drift condition still present |
| `DRIFT_REGRESSED` | New drift detected as a result of the repair |
| `DRIFT_INCONCLUSIVE` | Cannot determine drift state from available evidence |

Bounded re-check: inspect only the specific component/route/file referenced in the original finding. Full AG-31 re-audit is out of scope for AG-35.

---

## 6. Governance Reconciliation

AG-35 produces governance recommendations only. It does NOT mutate `drift_finding_status.json`.

### Recommended transitions

| Drift State | Verification | Recommendation |
|---|---|---|
| `DRIFT_CLEARED` | `PASSED` | `recommend_RESOLVED` |
| `DRIFT_CLEARED` | `INCONCLUSIVE` | `recommend_OPEN` (needs operator re-check) |
| `DRIFT_PERSISTS` | any | `recommend_ESCALATED_AGAIN` |
| `DRIFT_REGRESSED` | any | `recommend_HIGH_PRIORITY_ESCALATION` |
| `DRIFT_INCONCLUSIVE` | `FAILED` | `recommend_ESCALATED_AGAIN` |
| `DRIFT_INCONCLUSIVE` | `INCONCLUSIVE` | `recommend_OPEN` |

### Rule

AG-32 remains the lifecycle authority. AG-35 cannot call `escalate_finding()`, `resolve_finding()`, or any AG-32 write function. It only provides the recommendation; the operator feeds it back to AG-32.

---

## 7. Implementation Surface

Minimal surface only:

```
core/audit/repair_reconciliation.py          — verification + re-audit + recommendation engine
core/audit/reconciliation_store.py           — append-only log + atomic latest
interface/operator/api_repair_reconciliation.py  — Mission Control surface
core/verify/test_ag35_repair_reconciliation.py   — test suite
```

Patch:

```
interface/operator/mission_control_server.py — AG-35 route block (graceful fallback)
```

---

## 8. Runtime Outputs

| File | Type | Purpose |
|---|---|---|
| `$LUKA_RUNTIME_ROOT/state/repair_reconciliation_log.jsonl` | append-only JSONL | One record per reconciliation |
| `$LUKA_RUNTIME_ROOT/state/repair_reconciliation_latest.json` | atomic overwrite | Latest reconciliation summary |

Each reconciliation record must contain:

```json
{
  "ts": "...",
  "reconciliation_id": "recon-<hex>",
  "execution_id": "repair-exec-...",
  "finding_id": "...",
  "verification_status": "PASSED | FAILED | INCONCLUSIVE",
  "drift_state": "DRIFT_CLEARED | DRIFT_PERSISTS | DRIFT_REGRESSED | DRIFT_INCONCLUSIVE",
  "governance_recommendation": "recommend_RESOLVED | recommend_ESCALATED_AGAIN | ...",
  "evidence_refs": ["drift_repair_execution_log.jsonl", "..."],
  "operator_action_required": true
}
```

`operator_action_required` is always `true` — AG-35 never applies recommendations automatically.

---

## 9. Mission Control Integration

AG-35 exposes the following surfaces:

| Surface | Endpoint | Auth |
|---|---|---|
| Reconciliation history | `GET /api/repair_reconciliation/history` | none |
| Latest reconciliation | `GET /api/repair_reconciliation/latest` | none |
| Single reconciliation | `GET /api/repair_reconciliation/{reconciliation_id}` | none |
| Run reconciliation for execution | `POST /api/repair_reconciliation/run` | `operator_id` required |

---

## 10. Safety Constraints

| Rule | Constraint |
|---|---|
| Operator remains final authority | Recommendations only; no direct governance writes |
| operator_id required for POST | 403 without it |
| No auto-rollback | Regression detection triggers recommendation, not action |
| Kernel deterministic | No dynamic code changes |
| Evidence-first | No recommendation without reconciliation record |
| No baseline mutation | `audit_baseline.py` never touched |
| No finding mutation | `drift_finding_status.json` never touched |

---

## 11. Repair Lifecycle States (full taxonomy)

| State | Who sets it | Meaning |
|---|---|---|
| `PROPOSED` | AG-33 | Plan generated, awaiting operator review |
| `APPROVED` | Operator | Operator authorised execution |
| `EXECUTED` | AG-34 | Bounded repair ran, evidence recorded |
| `VERIFIED` | AG-35 | Post-repair verification passed |
| `FAILED` | AG-34 / AG-35 | Execution or verification failed |
| `RECONCILED` | AG-35 | Reconciliation record produced, recommendation issued |
| `REVERTED` | Operator | Explicit rollback action by operator |

---

## 12. Final Deliverables

### A. This document — `ag35_repair_verification_reconciliation.md`

### B. Executive verdict — why AG-35 is required after AG-34

AG-34 proves that a bounded repair ran and evidence was captured. But it cannot determine whether the original drift condition was actually resolved — it has no visibility into the AG-31 drift state or the relationship between the pre/post file hash change and the original finding's root cause. AG-35 closes this gap by cross-referencing execution evidence against drift detection state and emitting a formal reconciliation verdict that the operator can use to drive the final AG-32 lifecycle transition. Without AG-35, the repair stack has no verified feedback loop: repairs execute, but the system never confirms whether they worked.

### C. Top 5 reconciliation risks AG-35 must prevent

| # | Risk | Guard |
|---|---|---|
| 1 | Auto-closing findings after `DRIFT_CLEARED` | `operator_action_required=true` always; no direct AG-32 write calls |
| 2 | Regression blind spot — repair fixes A but breaks B | Bounded re-audit checks the full component, not just the patched file |
| 3 | False `DRIFT_CLEARED` from file hash change alone | Must cross-reference functional check (import/syntax/route) not just hash diff |
| 4 | Stale evidence reference — reconciliation runs against outdated execution record | Load execution record by `execution_id`, not by scanning latest |
| 5 | Silent `INCONCLUSIVE` spam — every reconciliation returns inconclusive | Inconclusive must include specific reason; operator is notified, not silently swallowed |

### D. Repair lifecycle state diagram

```
AG-33 generates
    PROPOSED
        ↓ operator approves
    APPROVED
        ↓ AG-34 executes
    EXECUTED
        ↓ AG-35 reconciles
    ┌───────────────────────┐
    │ verification_status:  │
    │   PASSED              │──→ RECONCILED (recommend_RESOLVED)
    │   FAILED              │──→ RECONCILED (recommend_ESCALATED_AGAIN)
    │   INCONCLUSIVE        │──→ RECONCILED (recommend_OPEN)
    └───────────────────────┘
    VERIFIED  (if operator confirms RESOLVED via AG-32)
    FAILED    (if AG-34 error or AG-35 FAILED verdict)
    REVERTED  (operator explicit rollback at any point)
```

---

## Architecture Position After AG-35

```
L11 [AG-31: Runtime Self-Audit]
L12 [AG-32: Drift Governance]
L13 [AG-33: Repair Planning]
L14 [AG-34: Supervised Repair Execution]
L15 [AG-35: Repair Verification + Governance Reconciliation]   ← this phase
     ↓ reconciliation record + governance recommendation
     → operator reviews
     → AG-32: RESOLVED | ESCALATED_AGAIN | OPEN
```

### System classification after AG-35

> Self-auditing runtime with governed drift review, structured repair planning, supervised repair execution, and verified governance reconciliation

Still NOT: autonomous self-healing architecture.
