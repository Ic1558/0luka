# 0LUKA Repository Structure

File: `docs/0LUKA_REPOSITORY_STRUCTURE.md`  
Version: `v1.0`  
Status: `Repository Organization Specification`

## 1. Purpose

This document defines the repository layout and structural boundaries of the 0luka platform.

The goals are:
- ensure clear separation of platform layers
- prevent runtime logic from mixing with domain logic
- maintain deterministic execution paths
- make the repository understandable for operators and contributors

This structure reflects the platform architecture defined in:
- `docs/0LUKA_PLATFORM_MODEL.md`

## 2. Top-Level Repository Layout

Typical repository structure:

```text
0luka/
│
├─ core/
├─ repos/
├─ interface/
├─ tools/
├─ observability/
├─ docs/
│
├─ runtime_root/
└─ tests/
```

Each directory corresponds to a platform responsibility layer.

## 3. `core/`

The core runtime control layer.

This directory contains the logic that defines how the platform executes workloads.

Typical contents:

```text
core/
  dispatcher/
  router/
  runtime_state/
  approval/
  execution_adapter/
  governance/
```

Responsibilities:
- task routing
- execution control
- approval gating
- runtime state transitions
- system invariants enforcement

Important rule:
- Domain engines must never modify core runtime behavior directly.

Core is the platform kernel.

## 4. `repos/`

The domain engine layer.

Each domain engine lives inside `repos/`.

Example:

```text
repos/
  qs/
     src/
       universal_qs_engine/
           job_registry.py
           jobs/
               boq_extract.py
               cost_estimate.py
               po_generate.py
               report_generate.py
     tests/
```

Responsibilities:
- domain-specific logic
- job handlers
- domain validation
- artifact generation

Domain engines must use the runtime interface:
- `run_registered_job(job_type, context)`

Domain engines must not bypass the runtime control plane.

## 5. `interface/`

The operator-facing layer.

This includes APIs and dashboards used by operators.

Example:

```text
interface/
   operator/
      mission_control_server.py
   api/
      runtime_api.py
```

Responsibilities:
- system monitoring
- operator visibility
- read-only projections
- administrative controls

Typical interfaces include:
- Mission Control
- health endpoints
- runtime inspection APIs

## 6. `tools/`

Operational and maintenance utilities.

Example:

```text
tools/
   ops/
      dispatcher_restart.sh
      projection_rebuild.py
   scripts/
      artifact_cleanup.py
```

Responsibilities:
- operational tasks
- maintenance scripts
- debug utilities
- recovery helpers

Important rule:
- tools must not implement business logic.

They only interact with the runtime.

## 7. `observability/`

Runtime monitoring and telemetry.

Example:

```text
observability/
   logs/
   metrics/
   traces/
```

Typical files:
- `activity_feed.jsonl`
- `runtime_events.jsonl`
- `guardian_actions.jsonl`

Responsibilities:
- runtime event logging
- system telemetry
- audit trails
- incident tracking

Observability ensures the system is auditable and traceable.

## 8. `docs/`

System documentation.

Example structure:

```text
docs/
   0LUKA_PLATFORM_MODEL.md
   0LUKA_REPOSITORY_STRUCTURE.md
   0LUKA_KERNEL_INVARIANTS.md
   0LUKA_STATE_MACHINE_SPEC.md
   0LUKA_RUNTIME_VALIDATOR.md
   0LUKA_RUNTIME_GUARDIAN.md
   0LUKA_RUNTIME_OPERATIONS.md
   0LUKA_DEPLOYMENT_MODEL.md
   MISSION_CONTROL_V2_SPEC.md
```

Responsibilities:
- architecture documentation
- platform laws
- runtime operations
- deployment models

This directory defines the formal platform specification.

## 9. `runtime_root/`

Runtime data directory.

Example:

```text
runtime_root/
   state/
   queue/
   artifacts/
   projections/
```

Contents are generated during execution.

Typical structure:
- `runtime_root/state/qs_runs/`
- `runtime_root/artifacts/`
- `runtime_root/outbox/`

Responsibilities:
- runtime state persistence
- artifact storage
- task queues
- read-model projections

Important rule:
- runtime data must never be committed to git.

## 10. `tests/`

All system tests.

Example:

```text
tests/
   core/
   qs/
   integration/
```

Typical test types:
- unit tests
- runtime integration tests
- state machine tests
- artifact validation tests

Tests ensure:
- runtime invariants hold
- job handlers behave deterministically
- platform contracts remain stable

## 11. Layer Boundary Rules

The repository structure enforces strict boundaries.

| Layer | Allowed to depend on |
|---|---|
| `core` | nothing higher |
| `repos` | core |
| `interface` | core + repos |
| `tools` | core + runtime |
| `observability` | runtime data |

Forbidden patterns:
- `repos` modifying core runtime logic
- `interface` bypassing runtime execution
- `tools` implementing domain business logic

## 12. Example Execution Flow Through Repository

A QS job execution touches the following layers:

```text
repos/qs/jobs/*
       ↓
core/execution_adapter
       ↓
core/runtime_state
       ↓
runtime_root/state
       ↓
observability/logs
       ↓
interface/operator
```

## 13. Repository Philosophy

The repository structure enforces four key principles.

Separation of Concerns:
- runtime control, domain logic, and operator interfaces must remain separate.

Deterministic Execution:
- all workloads must flow through the runtime kernel.

Observability:
- all actions must be traceable through logs and runtime state.

Extensibility:
- new domain engines can be added without modifying the runtime kernel.

Example:
- `repos/aec/`
- `repos/finance/`
- `repos/document/`

## 14. Example Future Repository

Future expansion might look like:

```text
repos/
   qs/
   aec/
   finance/
   document/
```

All engines use the same runtime execution model.

## Summary

The 0luka repository is structured to support a runtime execution platform with multiple domain engines.

The repository separates:
- core runtime control
- domain engines
- operator interfaces
- operational tools
- observability
- documentation

This structure ensures the system remains:
- deterministic
- auditable
- maintainable
- extensible
