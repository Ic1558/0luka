# 0LUKA Execution Model

File: `docs/0LUKA_EXECUTION_MODEL.md`  
Version: `v1.0`  
Status: `Runtime Execution Specification`

## 1. Purpose

This document defines the execution semantics of the 0luka runtime platform.

The execution model describes how a task moves through the platform from ingress to artifact production.

It explains:
- how runs are created
- how execution is authorized
- how handlers are invoked
- how artifacts are committed
- how system visibility is produced

This model connects the following specifications:
- `docs/0LUKA_PLATFORM_MODEL.md`
- `docs/0LUKA_STATE_MACHINE_SPEC.md`
- `docs/0LUKA_ARTIFACT_MODEL.md`
- `docs/0LUKA_RUNTIME_VALIDATOR.md`
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

## 2. Execution Overview

All workloads execute through a deterministic runtime path.

```text
Task Ingress
     ↓
Dispatcher
     ↓
Router Validation
     ↓
Run Creation
     ↓
Runtime State Initialization
     ↓
Approval Gate
     ↓
Handler Execution
     ↓
Artifact Commit
     ↓
Projection
     ↓
Mission Control Visibility
```

Direct execution outside this path is forbidden.

## 3. Execution Entities

### Task

A task represents a request for execution.

Example fields:
- `job_type`
- `project_id`
- `payload`
- `metadata`

Tasks enter the system through the dispatcher.

### Run

A run represents the execution instance of a task.

Each run has:
- `run_id`
- `job_type`
- `project_id`
- `status`
- `execution_status`
- `artifact_refs`
- `timestamps`

Runs are persisted in the runtime state.

### Handler

Handlers implement domain execution logic.

Handlers are resolved through the job registry.

Example:
- `qs.boq_extract`
- `qs.cost_estimate`
- `qs.po_generate`
- `qs.report_generate`

Handlers must obey runtime contracts.

## 4. Run Creation

When a task is accepted by the router, the runtime creates a run.

Example:

`run_id = run_YYYYMMDD_xxx`

Initial run state:
- `runtime_state = CREATED`
- `execution_status = pending`
- `artifact_refs = []`

The run becomes the execution container for the task.

## 5. State Machine Integration

Execution follows the runtime state machine.

Typical state progression:

```text
CREATED
 ↓
ACCEPTED
 ↓
PENDING_APPROVAL (optional)
 ↓
EXECUTING
 ↓
COMPLETED | FAILED
```

Invalid transitions are rejected by the validator.

Reference:
- `docs/0LUKA_STATE_MACHINE_SPEC.md`

## 6. Approval Gate

Certain job types require approval.

Example:
- `qs.po_generate`

Before approval:
- `execution_status = blocked`
- `job_execution_state = not_started`

After approval:
- `execution_status = allowed`

Execution begins only when allowed.

## 7. Handler Execution

When execution is permitted, the runtime invokes the handler.

Interface:

`run_registered_job(job_type, context)`

Context example:

```json
{
  "run_id": "run_20260309_001",
  "job_type": "qs.report_generate",
  "project_id": "PD17",
  "metadata": {}
}
```

Handlers must return:
- `artifact_refs`

Handlers must never fabricate artifacts.

## 8. Artifact Commit

Handler outputs are committed to runtime state.

Example:

```json
[
  {
    "artifact_type": "report",
    "path": "artifacts/qs/run_20260309_001/project_qs_report.md",
    "created_at": "2026-03-09T03:05:00Z"
  }
]
```

The runtime sidecar records these artifacts.

Reference:
- `docs/0LUKA_ARTIFACT_MODEL.md`

Artifacts become immutable once committed.

## 9. Projection

After execution completes, runtime data is projected to read models.

Projection flow:

```text
runtime sidecar
   ↓
outbox projection
   ↓
Mission Control read model
```

Example APIs:
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`

Projections are read-only.

## 10. Failure Handling

Execution failures are handled deterministically.

Examples:

Unknown job type:
- `execution_status = failed`
- `artifact_refs = []`

Handler error:
- `run_state = FAILED`
- `artifact_refs = []`

Artifact generation failure:
- `ARTIFACT_ERROR`

Failures must never produce synthetic artifacts.

## 11. Runtime Validation

The runtime validator ensures execution correctness.

Validator checks:
- state transitions
- artifact integrity
- approval enforcement
- projection consistency

If violations occur:
- validator raises error

Reference:
- `docs/0LUKA_RUNTIME_VALIDATOR.md`

## 12. Runtime Guardian

The guardian layer protects runtime stability.

Guardian actions may include:
- restart dispatcher
- rebuild projections
- mark run failed
- pause execution

Reference:
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

## 13. Observability

All execution steps must produce observable events.

Example event:

```json
{
  "event": "run_completed",
  "run_id": "run_20260309_001",
  "job_type": "qs.report_generate",
  "timestamp": "2026-03-09T03:05:00Z"
}
```

Event log location:

`observability/activity_feed.jsonl`

Observability ensures the system remains auditable.

## 14. Execution Guarantees

The execution model guarantees:
- deterministic runtime behavior
- artifact provenance integrity
- approval enforcement
- observable system state

These guarantees ensure the platform operates safely.

## 15. Example Execution

Example run:

task:
- `job_type = qs.cost_estimate`
- `project_id = PD17`

Execution sequence:

```text
task ingress
 → run created
 → execution allowed
 → handler executed
 → artifact_refs generated
 → runtime state updated
 → projection updated
 → Mission Control visible
```

## 16. Future Execution Enhancements

Possible future improvements:
- distributed worker execution
- parallel job execution
- artifact caching
- execution scheduling

All improvements must preserve:
- runtime invariants
- state machine semantics
- artifact provenance

## Summary

The execution model defines how the 0luka platform processes tasks into observable results.

Execution follows a controlled path:

```text
task
 → run
 → handler
 → artifact
 → projection
 → operator visibility
```

This model ensures the system remains:
- deterministic
- auditable
- safe
- extensible
