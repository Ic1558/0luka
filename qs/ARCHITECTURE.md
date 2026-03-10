# qs Architecture (Phase A)

## Layer Responsibilities

- **qs** is the **application layer**: domain workflows, business-oriented job contracts,
  and intent-level orchestration for tasks such as BOQ generation, compliance checks,
  and PO preparation.
- **0luka** is the **runtime/governance layer**: execution control, approvals/governance,
  queueing, and mission-level control plane behaviors.

This boundary is strict: qs should describe what work is needed, while 0luka governs
how and whether work is executed.

## Phase A Scope

Phase A introduces deterministic scaffolding only:

1. Job contracts (`qs/app/jobs.py`) for known job types.
2. Approval-sensitive boundary (`qs/app/policy.py`) with fail-closed behavior.
3. Integration adapter stubs (`qs/integration/oluka_*.py`) that do not import or couple
   to real 0luka runtime code.
4. Minimal status surface (`qs/app/status.py`) for operator visibility.

## What Phase A Does Not Do

- No live 0luka runtime integration.
- No governance migration into qs.
- No control plane or mission-control logic implementation.

Later phases can replace stubs with real adapters once runtime contracts are approved.
