# 0LUKA System Topology

## Purpose

This document defines the current topological map of the 0luka system.

It exists to provide one canonical architecture reference for:

- runtime structure
- observability surfaces
- reasoning and decision layers
- knowledge mirror integration
- frozen canonical boundaries
- future control-plane implementation constraints

This document reflects the system state after:

- Step 1 complete enough
- Step 2 interpreted read model live
- Phase C.0 dry-run classifier
- Phase C.1 decision preview
- Phase D bounded decision memory
- NotebookLM publish lane operational
- NotebookLM trigger repo-anchored
- Phase E control-plane blueprint documented

---

## Current Classification

0luka is currently a:

**clean bounded mainline + interpreted observability + dry-run classification + read-only decision preview + bounded decision memory + operational knowledge mirror**

It is **not yet**:

- an autonomous runtime
- a remediation engine
- a control-plane executor
- a self-mutating system

---

## Topology Overview

```text
Human Operator
    │
    ▼
Mission Control UI
    │
    ▼
Mission Control Server
    │
    ├── Read Model Projection
    │     ├── qs_runs
    │     ├── proof artifacts
    │     ├── activity feed
    │     ├── decision preview
    │     └── decision memory
    │
    ├── Interpretation Layer
    │     └── interpret_run(...)
    │
    ├── Classification Layer
    │     └── classify_once(...)
    │
    └── Decision Memory Layer
          ├── decision_log.jsonl
          └── decision_latest.json

Runtime Kernel
    ├── dispatcher
    ├── runtime workers
    ├── bridge consumers
    └── supporting deterministic runtime logic

Runtime State
    └── $LUKA_RUNTIME_ROOT
          ├── logs/
          ├── state/
          ├── artifacts/
          └── task outputs

Knowledge Mirror
    └── NotebookLM
          ├── ingest bundle
          ├── sealed state pack
          └── published mirror sources

Frozen Canonical Boundary
    └── repos/qs
```

## System Layers

### 1. Runtime Layer

Role:

The runtime layer executes deterministic work and produces raw system signals.

Examples:
- dispatcher
- runtime workers
- bridge consumers
- queue readers
- task execution surfaces

Characteristics:
- deterministic
- bounded
- no broad orchestration logic
- no autonomous control-plane behavior

### 2. Signal Layer

Role:

The signal layer exposes raw system state.

Examples:
- operator_status
- runtime_status
- policy_drift
- artifact presence / proof references
- activity feed entries

Characteristics:
- observational only
- no action semantics
- forms the input to interpretation and classification

### 3. Interpreted Observability Layer

Role:

This layer turns raw run/artifact state into meaningful interpreted signals.

Examples:
- artifact_count
- expected_artifacts
- missing_artifacts
- signal

Signal values currently supported:
- COMPLETE
- PARTIAL
- MISSING_PROOF
- INCONSISTENT

Characteristics:
- read-only
- derived from runtime state
- no mutation
- no remediation

### 4. Classification Layer (Phase C.0)

Role:

This layer performs dry-run classification over interpreted system signals.

Primary function:
- classify_once(...)

Current outputs:
- nominal
- drift_detected
- None

Characteristics:
- pure
- deterministic
- side-effect free
- no writes
- no loops
- no automation
- no runtime actions

### 5. Decision Preview Layer (Phase C.1)

Role:

This layer exposes classification results through a read-only preview surface.

Purpose:
- let operators and future systems inspect decision candidates
- keep reasoning visible without introducing persistence-driven action

Characteristics:
- read-only
- no control-plane behavior
- no remediation
- no action execution

### 6. Decision Memory Layer (Phase D)

Role:

This layer persists bounded decision history.

Artifacts:
- decision_log.jsonl
- decision_latest.json

Purpose:
- preserve reasoning history
- enable replay and audit
- create a foundation for future control-plane observability

Characteristics:
- bounded persistence only
- no remediation
- no automation
- no runtime mutation

### 7. Knowledge Mirror Layer

Role:

This layer mirrors system context into NotebookLM.

Pipeline:

```text
repo state
  -> notebook ingest bundle
  -> SOT seal
  -> publish
  -> NotebookLM
```

Current state:
- publish lane operational
- trigger repo-anchored
- machine/repo trigger state aligned

Purpose:
- external read replica of system state
- knowledge visibility
- portable context mirror

Characteristics:
- external mirror only
- not a control-plane component
- not an execution surface

### 8. Governance Boundary Layer

Role:

This layer constrains how the system evolves.

Includes:
- bounded PR discipline
- governance CI gates
- proof and DoD checks
- size/scope checks
- frozen canonical boundaries

Purpose:
- prevent drift
- prevent heavy-branch regression
- protect canonical engines
- preserve clean mainline evolution

## Mission Control Topology

Mission Control currently acts as a:

read-only observability and reasoning surface

It is not yet a control plane.

Current functions:
- render QS runs
- render proof/artifact relationships
- render interpreted signals
- render decision preview and memory surfaces
- expose read-only API surfaces

Current non-goals:
- no remediation controls
- no action triggers
- no runtime mutation
- no operator-side repair actions

## Runtime State Topology

Runtime state lives outside the git repository under:
- $LUKA_RUNTIME_ROOT

Typical structure:

```text
$LUKA_RUNTIME_ROOT/
  logs/
  state/
  artifacts/
  tasks/
```

Important rule:

Runtime state is operational state, not canonical code.

It may be observed, interpreted, and summarized, but it must remain clearly separated from repository source-of-truth.

## Frozen Canonical Boundary

Canonical external lane:
- repos/qs

Status:
- frozen canonical

Meaning:
- mainline evolution must not mutate this subsystem casually
- control-plane work must not write into canonical engines
- any integration with this boundary must remain read-only unless explicitly redesigned under separate governance

This is a hard architectural rule.

## Current Implemented Surfaces

Runtime / Observability:
- operator status
- runtime status
- policy drift
- activity feed
- proof artifact inventory
- proof artifact detail
- QS run list and detail
- per-run artifact listing

Mission Control:
- run list
- artifact detail
- interpreted signal rendering
- read-only decision preview surfaces

Classification:
- dry-run classifier

Decision Memory:
- persisted bounded decision history

Knowledge Mirror:
- NotebookLM ingest
- NotebookLM publish
- repo-anchored launchd trigger

## Current Non-Goals

The system still does not include:
- control-plane execution
- remediation engine execution
- automatic repair actions
- artifact mutation
- autonomous runtime behavior
- planner/executor live orchestration
- runtime state mutation from decision outputs

These remain future-phase concerns.

## Phase Map

Phase A  Runtime Signals        ✅
Phase B  Interpreted Model      ✅
Phase C0 Dry-Run Classifier     ✅
Phase C1 Decision Preview       ✅
Phase D  Decision Memory        ✅
Phase E  Control Plane          ⏳ blueprint only

## Future Topology

The future control-plane path is only conceptual at this time:

```text
Decision Memory
  -> Control Decision
  -> Remediation Candidate
  -> Execution Guard
  -> Action Audit
  -> System State Change
```

Important:

This topology is not implemented on main.

No current code path performs this sequence.

## Architectural Invariants

The following must remain true:
1. main remains clean and bounded.
2. repos/qs remains frozen canonical unless explicitly reopened by governance.
3. read-model and reasoning layers remain observable and auditable.
4. classification must remain deterministic unless explicitly redesigned.
5. decision memory must not imply autonomous execution.
6. knowledge mirror must not be confused with control-plane state.
7. future control-plane implementation must never bypass governance boundaries.

## Final Statement

0luka currently implements Observability + Reasoning + Decision Memory with an operational knowledge mirror.

It does not yet implement a live control plane or autonomous runtime action layer.
