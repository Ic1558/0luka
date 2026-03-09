# 0luka

0luka is a deterministic runtime platform designed to execute domain engines through a controlled execution pipeline.

The platform enforces:
- deterministic execution
- approval-gated operations
- artifact provenance
- runtime observability
- fail-closed safety guarantees

0luka is not a monolithic application.  
It is a runtime kernel + domain engine ecosystem.

## Platform Model

Execution inside 0luka always follows the same controlled path.

```text
Task
  ↓
Dispatcher
  ↓
Router
  ↓
Run Creation
  ↓
Approval Gate
  ↓
Handler Execution
  ↓
Artifact Commit
  ↓
Projection
  ↓
Mission Control
```

Direct execution outside this path is not allowed.

Reference:
- `docs/0LUKA_EXECUTION_MODEL.md`

## Core Principles

Deterministic Runtime:
- all workloads must execute through the runtime control plane.

Artifact Truth System:
- artifacts represent the observable outputs of execution and must remain immutable.

Approval Safety:
- certain operations require explicit approval before execution.

Observability:
- all runtime actions produce audit-grade logs and projections.

## Repository Structure

```text
0luka/
│
├─ core/
│    runtime kernel
│
├─ repos/
│    domain engines
│
├─ interface/
│    operator APIs + Mission Control
│
├─ tools/
│    operational utilities
│
├─ observability/
│    runtime logs and telemetry
│
├─ docs/
│    platform specification
│
├─ runtime_root/
│    runtime data (state, artifacts, projections)
│
└─ tests/
     platform tests
```

Full reference:
- `docs/0LUKA_REPOSITORY_STRUCTURE.md`

## Domain Engines

Domain engines extend the platform without modifying the runtime kernel.

Example engines:

```text
repos/
  qs/
  aec/
  finance/
  document/
```

Each engine provides:
- job registry
- job handlers
- artifact generation
- domain validation

Reference:
- `docs/0LUKA_EXTENSION_MODEL.md`

## Artifact System

Artifacts are immutable outputs produced by handlers.

Example:

```text
runtime_root/artifacts/
  qs/
    run_20260309_001/
      cost_estimate.json
```

Artifacts must always map to:
- `run_id`
- `job_type`
- `handler`
- `timestamp`

Reference:
- `docs/0LUKA_ARTIFACT_MODEL.md`

## Runtime Safety

0luka enforces safety through multiple layers.

```text
Kernel Invariants
     ↓
Runtime State Machine
     ↓
Runtime Validator
     ↓
Runtime Guardian
```

References:
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_RUNTIME_VALIDATOR.md`
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

## Mission Control

Mission Control provides read-only visibility into runtime state.

Example APIs:
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`

Capabilities:
- inspect runs
- view artifacts
- monitor runtime health

Reference:
- `docs/MISSION_CONTROL_V2_SPEC.md`

## Documentation Map

Platform documentation is organized as follows.

Platform:
- `docs/0LUKA_PLATFORM_MODEL.md`
- `docs/0LUKA_REPOSITORY_STRUCTURE.md`
- `docs/0LUKA_EXTENSION_MODEL.md`
- `docs/0LUKA_EXECUTION_MODEL.md`
- `docs/0LUKA_ARTIFACT_MODEL.md`

Runtime Laws:
- `docs/0LUKA_STATE_MACHINE_SPEC.md`
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_RUNTIME_INVARIANTS.md`

Runtime Control:
- `docs/0LUKA_RUNTIME_VALIDATOR.md`
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

Operations:
- `docs/0LUKA_RUNTIME_OPERATIONS.md`
- `docs/0LUKA_RUNBOOK.md`
- `docs/0LUKA_DEPLOYMENT_MODEL.md`
- `docs/0LUKA_OPERATOR_GUIDE.md`

Development:
- `docs/0LUKA_DEVELOPER_GUIDE.md`

## Quick Example

Example task execution.

`job_type: qs.cost_estimate`  
`project_id: PD17`

Runtime flow:

```text
task received
 → run created
 → handler executed
 → artifact generated
 → Mission Control visible
```

Result artifact:

`runtime_root/artifacts/qs/run_xxx/cost_estimate.json`

## Platform Guarantees

If the platform is functioning correctly:
- execution is deterministic
- artifacts are traceable
- runtime state is auditable
- failures are fail-closed

## License

Internal platform system.

## Summary

0luka is a runtime execution platform for domain engines.

The platform combines:
- runtime kernel
- control plane
- domain engines
- artifact system
- observability

to create a deterministic and auditable execution environment.
