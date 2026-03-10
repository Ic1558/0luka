# 0luka Repository Layer Map

## Purpose

This document defines the architectural layer boundaries of the 0luka repository.

Its goal is to prevent architectural drift by clarifying which parts of the repository belong to which system layer.

This document reflects the repository state after:

- Step 1 proof-consumption surfaces
- Step 2 decision-awareness design boundary
- stabilization of the mainline bounded workflow

## Current System Classification

The current system can be described as:

`a clean runtime kernel with observability and bounded decision awareness, but without an autonomous control plane`

The repository structure reflects this layered architecture.

## Layer Map

### 1. Kernel Layer

Location:

- `core/`

Role:

The kernel layer is the runtime execution substrate of the system.

It contains the deterministic runtime components responsible for executing work.

Examples:

- `core/task_dispatcher.py`
- `core/circuit_breaker.py`
- `core/remediation_engine.py`

Responsibilities:

- task execution
- runtime safety enforcement
- circuit breaking
- remediation triggers

Constraints:

- kernel must remain deterministic
- kernel must not embed broad orchestration logic
- kernel must not embed decision policy

### 2. Observability Layer

Locations:

- `tools/ops/`
- `interface/operator/mission_control_server.py`

Role:

The observability layer exposes runtime state to operators and tooling through read-only surfaces.

Examples:

- `/api/activity`
- `/api/runtime_status`
- `/api/operator_status`
- `/api/proof_artifacts`
- `/api/qs_runs`

Responsibilities:

- runtime status reporting
- activity feed inspection
- artifact and proof visibility
- run state inspection

Constraints:

- read-only surfaces only
- no runtime mutation
- no remediation triggers

### 3. Decision Awareness Layer (Phase C.0)

Location:

- `tools/ops/decision_engine.py`

Role:

This layer introduces bounded self-interpretation of system state.

Current capability:

- `classify_once(...)`

Supported outputs:

- `nominal`
- `drift_detected`
- `None`

Properties:

- pure function
- no side effects
- no persistence
- no remediation
- no queue mutation

This layer provides interpretation but not autonomous action.

### 4. Operator Surface

Location:

- `interface/`

Role:

The operator surface exposes system state to human operators.

Example components:

- `interface/operator/templates/mission_control.html`
- `interface/operator/mission_control_server.py`

Capabilities:

- proof consumption UI
- QS run inspection
- artifact viewing
- activity timeline inspection

Constraints:

- read-only surfaces
- no approval actions
- no remediation actions
- no autonomy controls

### 5. Runtime State Layer

Location:

- `$LUKA_RUNTIME_ROOT/`

Example structure:

- `logs/activity_feed.jsonl`
- `artifacts/tasks/`
- `state/`

Role:

The runtime root stores system state generated during execution.

Examples:

- activity feed
- task artifacts
- verification results
- runtime status snapshots

Constraints:

- append-only where possible
- atomic writes required
- runtime root is not part of the git repository

### 6. Canonical External Lane

Location:

- `repos/qs/`

Role:

This directory contains the canonical QS reference lane.

Current status:

- frozen canonical lane

Constraints:

- no mutation by mainline evolution
- no architectural coupling
- treated as external canonical reference

## Layer Interaction Graph

Current architecture:

```text
Human Operator
      |
      v
Mission Control (interface/)
      |
      v
API surfaces (observability)
      |
      +-- activity feed
      +-- proof artifacts
      +-- qs runs
      |
      v
Decision awareness (classify_once)
      |
      v
Kernel runtime (core/)
      |
      v
Runtime state ($LUKA_RUNTIME_ROOT)
```

Important boundary:

`Decision -> Action`

This boundary is not yet implemented.

## Explicit Non-Layers (Not Present Yet)

The following system capabilities do not currently exist on mainline:

- autonomous remediation loop
- decision persistence
- planner / executor separation
- policy-based autonomous execution
- queue mutation from decision outputs

These belong to future architecture steps.

## Architectural Invariants

The following constraints must remain true:

1. `main` must remain clean and bounded.
2. historical branches remain reference only.
3. `repos/qs` remains frozen canonical.
4. kernel must remain deterministic.
5. decision awareness must remain side-effect free until explicitly expanded.

## Why This Document Exists

Without explicit layer boundaries, the repository historically experienced:

- architectural drift
- feature placement confusion
- cross-layer coupling
- heavy branch gravity

This document exists to prevent those issues from recurring.

## Final Classification

Current system status:

`stable observable platform with bounded decision awareness`

Not yet:

`autonomous control plane`
