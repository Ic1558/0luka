# 0LUKA System Topology

## Current System Classification

`clean bounded mainline + interpreted observability + dry-run classification + read-only decision preview + bounded decision memory + operational knowledge mirror`

## Purpose

This document is the canonical topology map of the current 0luka system.

It is optimized for visual structure:

- runtime topology
- observability topology
- reasoning topology
- decision memory topology
- knowledge mirror topology
- frozen canonical boundary

## High-Level Architecture

```text
Human Operator
        │
        ▼
Mission Control UI
        │
        ▼
Mission Control Server
        │
        ▼
Runtime + Observability Pipeline
```

## Core Runtime -> Decision Flow

```text
Runtime
  │
  ▼
Signals
  │
  ▼
Interpreted Observability
  │
  ▼
Dry-Run Classification
  │
  ▼
Decision Preview
  │
  ▼
Decision Memory
```

## Runtime Topology

```text
Runtime Kernel
  ├ dispatcher
  ├ runtime workers
  ├ queue consumers
  └ bridge integrations

Runtime State

$LUKA_RUNTIME_ROOT
  ├ logs
  ├ state
  ├ artifacts
  └ task outputs
```

## Mission Control Topology

```text
Mission Control UI
        │
        ▼
Mission Control Server
        │
        ├ Run List
        ├ Artifact Inventory
        ├ Interpreted Signals
        ├ Decision Preview
        └ Decision Memory
```

Mission Control is currently a `read-only observability and reasoning surface`, not a control plane.

## Reasoning Layer Topology

```text
Interpretation Layer
      │
      ▼
Signal Derivation
      │
      ▼
Classification Layer
      │
      ▼
Decision Preview
```

Functions:

- `interpret_run(...)`
- `classify_once(...)`

## Decision Memory Topology

```text
Decision Memory

decision_log.jsonl
decision_latest.json
```

Properties:

- bounded persistence
- audit and replay support
- no remediation execution

## Knowledge Mirror Topology

```text
Repository
   │
   ▼
NotebookLM Ingest
   │
   ▼
NotebookLM Publish
   │
   ▼
Knowledge Mirror

Launchd Trigger
com.0luka.notebook_sync.plist

State
repo-anchored
```

## Governance Boundary

```text
Main Repository
   │
   ├ Runtime / Observability
   ├ Reasoning
   ├ Decision Memory
   │
   └ Frozen Boundary
        repos/qs
```

`repos/qs` remains frozen canonical.

## System Layers

```text
1. Runtime Layer
2. Signal Layer
3. Interpreted Observability Layer
4. Classification Layer (Phase C.0)
5. Decision Preview Layer (Phase C.1)
6. Decision Memory Layer (Phase D)
7. Knowledge Mirror Layer
8. Governance Boundary Layer
```

## Runtime Layer

```text
Produces deterministic work outputs
        │
        └── raw runtime signals
```

## Signal Layer

```text
operator_status
runtime_status
policy_drift
artifact_state
activity feed
```

## Interpreted Observability Layer

```text
artifact_count
expected_artifacts
missing_artifacts
signal

signal values:
COMPLETE
PARTIAL
MISSING_PROOF
INCONSISTENT
```

## Classification Layer (Phase C.0)

```text
classify_once(...)
   ├ nominal
   ├ drift_detected
   └ None
```

Properties:

- pure
- deterministic
- side-effect free
- no writes
- no loops
- no automation

## Decision Preview Layer (Phase C.1)

```text
Read-only decision candidate surface
        │
        └── no persistence-driven action
```

## Decision Memory Layer (Phase D)

```text
Persisted bounded reasoning history
        │
        ├ decision_log.jsonl
        └ decision_latest.json
```

## Knowledge Mirror Layer

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

## Runtime State Topology

```text
$LUKA_RUNTIME_ROOT/
  logs/
  state/
  artifacts/
  tasks/
```

Runtime state is operational state, separate from repository source-of-truth.

## Frozen Canonical Boundary

```text
Canonical external lane
  └ repos/qs
```

This boundary remains read-only for current mainline evolution.

## Current Implemented Surfaces

```text
Runtime / Observability
  ├ operator status
  ├ runtime status
  ├ policy drift
  ├ activity feed
  ├ proof artifact inventory/detail
  └ qs run list/detail

Mission Control
  ├ interpreted signal rendering
  ├ decision preview
  └ decision memory surfaces

Knowledge Mirror
  ├ NotebookLM ingest
  ├ NotebookLM publish
  └ repo-anchored launchd trigger
```

## Current Non-Goals

```text
No control-plane execution
No remediation engine execution
No automatic repair actions
No artifact mutation
No autonomous runtime behavior
No planner/executor live orchestration
No runtime mutation from decision outputs
```

## Phase Map

```text
Phase A  Runtime Signals        ✅
Phase B  Interpreted Model      ✅
Phase C0 Dry-Run Classifier     ✅
Phase C1 Decision Preview       ✅
Phase D  Decision Memory        ✅
Phase E  Control Plane          ⏳ blueprint only
```

## Future Control Plane Topology (Conceptual)

```text
Decision Memory
      │
      ▼
Control Decision
      │
      ▼
Remediation Candidate
      │
      ▼
Execution Guard
      │
      ▼
Action Audit
      │
      ▼
System State Change
```

This topology is not implemented.

## Architectural Invariants

- main remains clean and bounded
- repos/qs remains frozen canonical
- classification remains deterministic
- decision memory does not imply automation
- knowledge mirror is not control-plane state

## Final Statement

`0luka currently implements Observability + Reasoning + Decision Memory with an operational knowledge mirror.`

`Control-plane execution remains a future phase.`
