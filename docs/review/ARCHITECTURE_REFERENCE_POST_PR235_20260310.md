# 0luka Architecture Reference (Post-PR #235)

## Current Mainline Status

- mainline clean
- Mission Control read surfaces present
- Phase C.0 present as no-write dry-run classifier
- Phase D absent / parked
- `repos/qs` frozen canonical

## Architecture Layers

### 1. Kernel

The Kernel layer is the active runtime substrate of 0luka. It includes bounded runtime workers and execution components such as:

- `core.task_dispatcher`
- `tools/bridge/bridge_consumer.py`
- librarian worker surfaces under `tools/librarian/`
- other bounded runtime workers already active on main

This layer executes work and maintains runtime behavior, but it does not yet form a general autonomous decision loop.

### 2. Observability

The Observability layer exposes current runtime state through read-only surfaces on mainline. Examples include:

- `/api/operator_status`
- `/api/runtime_status`
- `/api/activity`
- `/api/proof_artifacts`
- `/api/qs_runs`
- activity feed surfaces
- runtime status reports
- proof/state read surfaces

This layer makes the system observable and inspectable without mutating runtime state.

### 3. Decision (Phase C.0)

Phase C.0 is now present in the narrowest safe form on mainline:

- `tools/ops/decision_engine.py`
- pure function: `classify_once(...)`

Supported outputs only:

- `nominal`
- `drift_detected`
- `None`

Current guarantees:

- no writes
- no endpoint
- no persistence
- no queue/remediation behavior
- no guardian coupling
- no Phase D spillover

This is bounded self-interpretation only.

### 4. Autonomy

Autonomy is absent on mainline and intentionally parked.

There is currently:

- no active remediation/action-selection loop
- no decision persistence contract
- no autonomous runtime action path derived from Phase C.0 outputs

## True Agent Boundary

On current mainline, the human operator remains the only true agent.

The system now has bounded self-interpretation through Phase C.0, but it still does not autonomously act on interpreted state.

## Canonical Graph

```text
Human Operator
  -> Mission Control
    -> API server
      -> Kernel workers
      -> Observability/state surfaces
      -> Decision classifier (Phase C.0)
      -> Autonomy boundary absent
      -> repos/qs frozen boundary
```

## Non-Claims

- this note does not unpark Phase D
- this note does not imply persistence or `/api/decisions`
- this note does not promote historical reference branches
- this note does not alter `repos/qs`

## Final Classification

stable observable platform with bounded decision awareness
