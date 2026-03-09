# 0LUKA Kernel Invariants

## 1. Definition of Kernel Invariant

Kernel invariants are non-negotiable platform laws that every 0luka runtime instance must satisfy at all times.

These laws are above:
- runtime behavior details
- filesystem layout decisions
- implementation-specific mechanisms

They constrain architecture and execution authority.  
If any kernel invariant is violated, the runtime must be treated as invalid or corrupted.

## 2. Execution Control Invariants

### Execution Path Control

All domain engine execution must occur through the controlled runtime path:

`dispatcher -> router -> execution adapter -> domain job handler`

Direct invocation of domain handlers outside this runtime path is forbidden.

### Single Execution Authority

The dispatcher is the only component authorized to initiate execution.

No secondary executor may bypass dispatcher authority.

### Controlled Lifecycle

Every execution must obey the official runtime lifecycle contract.

Reference: `docs/0LUKA_STATE_MACHINE_SPEC.md`

## 3. State Integrity Invariants

### Single State Truth

Each run must have exactly one authoritative runtime state.

### State Monotonicity

State transitions must move forward according to the state machine; rollback transitions are not valid state evolution.

### Terminal State Finality

`ARCHIVED` is terminal.  
A run in `ARCHIVED` cannot transition to any other state.

## 4. Approval Safety Invariants

### Approval Required Guarantee

If a job is approval-gated, execution must not begin until approval is granted.

### Approval Authority

Approval decisions must originate from an operator action or an approved control interface.

Untrusted or implicit approval sources are invalid.

## 5. Artifact Provenance Invariants

### Artifact Origin

Artifacts must originate from domain job handler execution.

### Runtime Non-Fabrication

The runtime must not fabricate artifact references.

### Artifact Immutability

Artifacts produced by a completed run are immutable from the perspective of runtime truth.

## 6. Truth Source Invariants

### Single Source of Truth

Runtime sidecar state is authoritative for run truth.

### Projection Non-Authority

Read models and projections (including Mission Control) are derived views and must not override runtime truth.

## 7. Determinism Invariants

### Deterministic Execution

Given equivalent inputs and equivalent environment constraints, execution must produce equivalent state transition outcomes.

### Reproducibility

Execution must remain auditable and reproducible through recorded runtime events and artifacts.

## 8. Auditability Invariants

### Event Emission

Every state transition must emit an audit event.

### Traceability

Every artifact must be traceable to a `run_id`.

## 9. Failure Safety Invariants

### Fail Closed

Invalid or unauthorized tasks must be rejected, not partially executed.

### Isolation

Failure of one run must not corrupt runtime truth or execution integrity of other runs.

## 10. Kernel Invariant Summary

The 0luka platform is governed by the following kernel laws:

- Execution control
- State integrity
- Approval safety
- Artifact provenance
- Truth source integrity
- Determinism
- Auditability
- Failure safety

These laws define the constitutional boundary of the platform.  
All runtime, operations, and implementation documents must remain subordinate to these invariants.

