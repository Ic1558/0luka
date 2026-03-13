# 0LUKA Capability Map (Canonical Contract)

Status: CANONICAL  
Authority: System Governance Contract  
Scope: Current capabilities only (not roadmap)

This document defines the authoritative capability contract of the 0luka system.

Any implementation, UI surface, or roadmap item must remain consistent with the
capability boundaries defined here.

Changes to this document require governance review.

## Canonical Governance Rules

1. This document describes current system capability only.
2. Future roadmap items must not be added here until implemented.
3. Implementation may not exceed capability authority defined here.
4. Operator interfaces must respect execution boundaries defined here.
5. Any change to capability authority requires governance phase change.

## 1. System Classification

0luka is currently a governed runtime system with:

- deterministic kernel evidence
- explicit policy governance
- supervised runtime remediation
- supervised autonomy candidates
- read-only operator decision intelligence

It is not an autonomous execution platform. It is a supervised runtime governance system with bounded candidate preparation and explicit operator-controlled execution gates.

## 2. Capability Categories

### Kernel Capabilities

- append-only runtime evidence logging
- deterministic execution state projection
- fail-closed runtime safety enforcement
- stable artifact placement in repo/runtime state paths

### Policy Governance Capabilities

- append-only policy proposal ledger
- policy approval, deploy, rollback, and override governance
- active policy version tracking
- policy preflight validation
- policy feedback signals derived from runtime evidence

### Runtime Governance Capabilities

- runtime lane state visibility
- remediation proposal, bridge, approval, and execution chain
- supervised execution with idempotency guards
- multi-lane remediation coordination through explicit `lane_targets`
- execution state and execution observability projections

### Mission Control / Operator Capabilities

- Mission Control read models for runtime, policy, remediation, and candidate state
- explicit operator runtime controls for freeze/pause runtime behavior
- explicit operator actions for candidate promotion and candidate lifecycle management
- explicit operator-gated remediation approval and execution APIs

### Supervised Autonomy Capabilities

- supervised autonomy candidate creation
- candidate ranking and observability
- candidate lifecycle state management
- candidate promotion into the governed remediation lifecycle

### Decision Intelligence Capabilities

- deterministic urgency, impact, recurrence, and risk bands for candidates
- bounded decision hints derived from current evidence only
- compact evidence summaries tied to candidate ranking, feedback, and execution history

## 3. Capability Table

| Capability | Layer | Current State | Authority Level | Execution Boundary | Evidence Surface |
| --- | --- | --- | --- | --- | --- |
| Append-only kernel event logging | Kernel | Active | System | No execution power | `observability/logs/*.jsonl` |
| Deterministic execution state projection | Kernel / Runtime | Active | System | Read model only | execution state projections, execution logs |
| Policy proposal / approval / deploy / rollback / override | Control Plane | Active | Operator-governed | Explicit policy APIs only | policy proposal ledger, version ledger, deployment ledger |
| Policy preflight validation | Control Plane | Active | System + Operator | Blocks invalid deploy/rollback values | policy preflight responses, policy audit events |
| Active policy binding to runtime | Runtime Governance | Active | Policy-governed | Read-only from runtime | active policy surface, policy snapshots |
| Runtime lane recommendation | Runtime Governance | Active | System-prepared, operator-visible | Recommendation only | runtime lane events, policy snapshots, guard telemetry |
| Remediation proposal generation | Runtime Governance | Active | System-prepared | Proposal only, no execution | remediation proposal ledger |
| Remediation selection | Runtime Governance | Active | Operator | Selection only | remediation selection ledger |
| Remediation bridge classification | Runtime Governance | Active | System | `EXECUTION_READY` or `BLOCKED`; no execution | remediation bridge ledger |
| Remediation approval gate | Runtime Governance | Active | Operator | Approval only, no execution | remediation approval ledger |
| Remediation execution | Runtime Governance | Active | Operator | Explicit execute call required | remediation execution ledger |
| Multi-lane remediation execution | Runtime Governance | Active | Operator | Explicit `lane_targets`; per-target-lane execution only | multi-lane execution rows, `execution_group_id` |
| Operator runtime freeze/pause controls | Mission Control / Runtime | Active | Operator | Gates runtime remediation execution only | operator runtime control ledger |
| Supervised autonomy candidate creation | Supervised Autonomy | Active | System-prepared | Candidate only, no promotion/execution | supervised autonomy candidate ledger |
| Candidate promotion to remediation proposal | Supervised Autonomy | Active | Operator | Explicit promotion only | candidate promotion ledger + remediation proposal ledger |
| Candidate lifecycle management | Supervised Autonomy | Active | Operator | Dismiss / resolve / archive only | candidate lifecycle ledger |
| Candidate ranking / observability | Supervised Autonomy | Active | Read-only | No lifecycle or execution power | candidate observability read models |
| Operator decision intelligence | Decision Intelligence | Active | Read-only | Decision support only | decision-support read models |

## 4. Explicit Non-Capabilities

0luka does not currently do the following:

- no automatic policy mutation
- no automatic policy proposal creation
- no automatic policy deploy, rollback, or override
- no autonomous remediation loop
- no automatic remediation execution
- no automatic candidate promotion
- no automatic candidate dismissal, resolution, or archival
- no hidden execution path outside the explicit bridge -> approval -> execute chain
- no distributed bypass of per-runtime idempotency contracts
- no ML, LLM, or probabilistic ranking inside runtime governance or decision support

## 5. Canonical System Invariants

The following invariants are canonical and must remain true:

- candidate lifecycle state must be append-only derived, not mutable row state
- Mission Control controls must never bypass the same API gates used by tests
- multi-lane execution idempotency must remain per-target-lane
- intelligence may recommend, but execution power expands only through explicit governance phases
- every new lane or proposal class must inherit append-only evidence, read models, and fail-closed guards
- runtime may read governed policy, but runtime may not mutate governed policy
- supervised autonomy candidates remain advisory until explicit operator promotion
- remediation execution always requires the governed chain: selection -> bridge -> approval -> explicit execution call

## 6. Authority Scope

This document is the authoritative description of:

- execution authority
- runtime governance boundaries
- operator vs system responsibility
- autonomy limits

If code, UI behavior, or documentation conflicts with this document, this document takes precedence until governance review updates it.

## 7. Current Phase Position

Current position in the implementation tree:

- supervised autonomy layer complete through candidate lifecycle management
- operator decision intelligence active as read-only decision support
- supervised remediation execution active behind explicit bridge, approval, idempotency, and operator runtime control gates

This places 0luka in a supervised autonomy runtime stage, not a self-governing autonomous runtime stage.

## 8. Current System Phase

- Kernel layer: complete
- Runtime governance: active
- Supervised autonomy: active
- Operator decision intelligence: read-only

Current phase: 10.1

## 9. Safety Boundary Summary

The following remain operator-only:

- policy proposal approval, deploy, rollback, and override
- candidate promotion
- candidate dismissal, resolution, and archival
- remediation approval for execution
- remediation execution
- operator runtime freeze / unfreeze and pause / resume actions

The system may:

- observe
- summarize
- rank
- recommend
- classify bounded remediation candidates

The system may not:

- promote automatically
- approve automatically
- execute automatically
- mutate policy automatically

## 10. Current Surfaces Tied To This Contract

This capability map corresponds to the current tree’s active surfaces:

- Mission Control policy, runtime lane, remediation, candidate, and decision-support panels
- read-only runtime and policy feedback projections
- explicit POST-only governance actions for promotion, lifecycle, approval, runtime control, and supervised execution
- append-only evidence ledgers across policy, runtime, remediation, and supervised autonomy layers

## 11. Repo Protection Note

This file should be treated as a protected architecture governance document.

Recommended repository handling:

- PR review required for changes to this file
- architecture tag required on PRs that modify this file

This phase records the protection requirement as part of the contract. It does not add new repository enforcement machinery.

## 12. Contract Intent

This document is the canonical current-state capability contract for:

- roadmap interpretation
- implementation boundary checks
- operator expectation setting
- future phase reviews

It describes what 0luka can do now, what remains operator-gated, and what the system explicitly does not do.
