# Antigravity Runtime Execution Plan (Supervised) (2026-03-13)

## 1. Purpose

Define an execution-grade, supervised sequence for runtime drift remediation
after explicit execution approval.

## 2. Preconditions for execution approval

Execution may be considered only when all conditions are true:

- runtime remediation plan is approved
- single supervising owner decision is approved
- entrypoint strategy decision is approved (restore or canonical repoint)
- responsible operator and change window are defined
- rollback owner and stop authority are defined

## 3. Execution boundary

- No action is authorized by this document alone.
- Runtime mutation requires explicit approval.
- Broker auth repair remains separate from runtime remediation.

## 4. Step-by-step supervised execution sequence

1. Confirm approved single supervisor owner (launchd or PM2).
2. Disable historical or secondary supervisor according to approved owner.
3. Apply approved entrypoint strategy:
   - restore maintained entrypoint on disk, or
   - repoint runtime command to maintained canonical path.
4. Confirm runtime working directory remains canonical (`repos/option`).
5. Confirm runtime process args match approved canonical entrypoint.
6. Confirm service bind on port 8089.
7. Confirm API health (`/api/status`, `/api/contract`).
8. Confirm history artifact continuity at
   `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`.

## 5. Verification after each step

After each supervised step, capture:

- applied step and timestamp
- expected state
- observed state
- pass or fail decision
- operator and reviewer identity

Proceed only if the current step passes.

## 6. Rollback conditions

Rollback is required if any condition occurs:

- no confirmed single-supervisor state
- entrypoint path not maintained on disk after change
- process args diverge from approved canonical path
- port 8089 not healthy
- API response loss for `/api/status` or `/api/contract`
- history artifact continuity cannot be proven

## 7. Stop conditions

Stop execution immediately when:

- evidence is contradictory
- approval boundary is unclear
- rollback owner is unavailable
- broker auth remediation is being mixed into runtime remediation acceptance

## 8. Evidence collection requirements

Evidence set must include:

- supervisor state before and after execution
- process args before and after execution
- working directory verification
- port 8089 verification
- API verification for `/api/status` and `/api/contract`
- history artifact continuity verification

All evidence must be preserved as read-only records.

## 9. Explicit non-goals

- no broker auth fix in this execution plan
- no trading logic changes
- no runtime feature changes
- no UI redesign

## 10. Approval requirement

Execution is blocked until explicit approval is granted for runtime mutation.
Without explicit approval, this document remains planning-only.
