# 0luka Control Plane Blueprint (Phase E)

## Current system state

The current system is:

`Observability + Reasoning + Decision Memory`

The system intentionally does NOT yet implement:

- control plane
- remediation engine
- automation loop
- artifact mutation

## Control plane concept

The conceptual system pipeline is:

Runtime
-> Signals
-> Interpreted
-> Classified
-> Decision Preview
-> Decision Memory
-> (Future) Control Plane

## Decision-to-action model

The future decision-to-action flow is expected to be:

Decision Memory
-> Control Decision
-> Remediation Candidate
-> Execution Engine
-> System State Change

This flow does not yet exist in code.

## Safety boundaries

Any future control plane must preserve these boundaries:

- decisions must originate from persisted decision memory
- remediation must be idempotent
- `repos/qs` remains frozen canonical
- remediation must not mutate canonical engines
- automation must be observable

## Control plane components (future)

The future control plane is expected to separate into these conceptual modules:

- `control_plane_router`
  - turns persisted decision state into bounded control decisions
- `remediation_registry`
  - defines allowed remediation candidates and their contracts
- `execution_guard`
  - validates preconditions, safety gates, and scope before any action runs
- `action_audit_log`
  - records control-plane actions and outcomes for later inspection

These are design components only. They are not implemented in this phase.

## Control-plane observability

Any future action layer should remain observable through explicit artifacts such as:

- `control_action_log.jsonl`
- `remediation_events`
- `mission_control_action_surface`

These are conceptual only in this blueprint.

## Phase map

Phase A  Runtime Signals        ✅
Phase B  Interpreted Model      ✅
Phase C0 Dry-Run Classifier     ✅
Phase C1 Decision Preview       ✅
Phase D  Decision Memory        ✅
Phase E  Control Plane          ⏳ (design only)

## Canonical boundary

`repos/qs` remains frozen canonical

The control plane must never mutate canonical engines.

## Architecture diagram

```text
Runtime
  ↓
Signals
  ↓
Interpreted
  ↓
Mission Control Read Model
  ↓
Classified
  ↓
Decision Preview
  ↓
Decision Memory
  ↓
(Future) Control Plane
```

## Final architectural statement

0luka currently implements Observability + Reasoning + Decision Memory.  
Control Plane capabilities remain a documented future phase.
