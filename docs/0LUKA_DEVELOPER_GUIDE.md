# 0LUKA Developer Guide

File: `docs/0LUKA_DEVELOPER_GUIDE.md`  
Version: `v1.0`  
Status: `Platform Development Guide`

## 1. Purpose

This document provides guidance for developers building domain engines and job handlers on the 0luka platform.

The guide explains:
- how to create a new engine
- how to implement job handlers
- how to integrate with the runtime execution model
- how to produce valid artifacts
- how to test runtime behavior

Developers must follow this guide to ensure compatibility with the 0luka runtime platform.

## 2. Platform Philosophy

0luka is designed as a runtime platform with pluggable domain engines.

Key principles:
- core runtime is stable
- domain logic lives in engines
- execution must pass through runtime
- artifacts must remain traceable

Developers must never bypass the runtime control plane.

## 3. Engine Development Model

A domain engine implements business logic on top of the runtime platform.

Example engines:
- QS engine
- AEC engine
- Finance engine
- Document engine

Each engine contains:
- job registry
- job handlers
- domain validation
- artifact generation

Reference:
- `docs/0LUKA_EXTENSION_MODEL.md`

## 4. Engine Directory Structure

All engines reside under:

`repos/<engine_name>/`

Example:

```text
repos/qs/
   src/
      universal_qs_engine/
         job_registry.py
         handlers/
            boq_extract.py
            cost_estimate.py
            po_generate.py
            report_generate.py
   tests/
```

Typical structure:

```text
repos/<engine>/
   src/
      engine/
         job_registry.py
         handlers/
   tests/
```

## 5. Job Registry

Each engine must implement a deterministic job registry.

Example:

`job_type → handler`

Example registry:
- `qs.boq_extract`
- `qs.cost_estimate`
- `qs.po_generate`
- `qs.report_generate`

Example implementation:

```python
JOB_REGISTRY = {
    "qs.boq_extract": boq_extract_handler,
    "qs.cost_estimate": cost_estimate_handler,
    "qs.po_generate": po_generate_handler,
    "qs.report_generate": report_generate_handler,
}
```

Unknown jobs must fail closed.

## 6. Handler Interface

Handlers implement domain logic.

All handlers must follow the execution contract.

Function signature:

```python
def handler(context):
    ...
```

Context example:
- `run_id`
- `job_type`
- `project_id`
- `metadata`

Handlers must return:
- `artifact_refs`

Example return:

```python
return [
    {
        "artifact_type": "cost_estimate",
        "path": "artifacts/qs/run_20260309_001/cost_estimate.json",
        "created_at": timestamp
    }
]
```

## 7. Artifact Contract

Artifacts represent the output of a job execution.

Reference:
- `docs/0LUKA_ARTIFACT_MODEL.md`

Artifacts must include:
- `artifact_type`
- `path`
- `created_at`

Optional fields:
- `checksum`
- `metadata`

Artifacts must be immutable.

## 8. Approval Handling

Some jobs require approval before execution.

Example:
- `qs.po_generate`

When approval is required:

`execution_status = blocked`

Handlers must not execute until approval is granted.

Reference:
- `docs/0LUKA_EXECUTION_MODEL.md`

## 9. Runtime Execution Path

All jobs execute through the runtime platform.

Execution flow:

```text
task ingress
 → dispatcher
 → router
 → run creation
 → approval gate
 → handler execution
 → artifact commit
 → projection
```

Developers must never call handlers directly.

## 10. Runtime Invariants

All engines must obey platform invariants.

Reference:
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_RUNTIME_INVARIANTS.md`

Examples:
- fail closed on unknown job
- no synthetic artifacts
- deterministic handler execution

Violations may cause runtime rejection.

## 11. Error Handling

Handlers must fail safely.

Example:

```python
try:
    result = generate_artifact()
except Exception:
    return []
```

Runtime will mark the run as `FAILED`.

Handlers must never fabricate artifacts.

## 12. Testing Requirements

Every engine must include tests.

Test types:
- handler unit tests
- artifact validation tests
- runtime integration tests

Example test directory:
- `repos/qs/tests/`

Tests should verify:
- artifact correctness
- runtime compatibility
- deterministic behavior

## 13. Artifact Storage

Artifacts must be written to runtime storage.

Example location:

`runtime_root/artifacts/`

Example structure:

```text
runtime_root/artifacts/
   qs/
      run_20260309_001/
         cost_estimate.json
```

Artifacts must match artifact references returned by the handler.

## 14. Logging

Handlers may log execution details.

Logs should include:
- `run_id`
- `job_type`
- `timestamp`
- `event`

Logs help debugging and auditing.

## 15. Adding a New Job

Steps:

Step 1:
- create handler: `handlers/new_job.py`

Step 2:
- register job type in `job_registry.py`

Step 3:
- write tests in `tests/test_new_job.py`

Step 4:
- verify runtime execution

## 16. Example Job

Example job:
- `qs.cost_estimate`

Execution:

```text
task received
 → run created
 → handler executed
 → artifact generated
 → runtime state updated
```

Result artifact:
- `cost_estimate.json`

## 17. Development Best Practices

Developers should follow these guidelines.

Deterministic behavior:
- handlers must produce predictable results.

Fail closed:
- unknown jobs must fail safely.

Artifact integrity:
- artifacts must always match artifact references.

Runtime compatibility:
- handlers must integrate with the runtime execution model.

## 18. Debugging

Common debugging steps:
- check runtime state
- check artifact paths
- check activity logs
- inspect handler output

Logs and runtime state provide insight into execution failures.

## 19. Future Engine Development

Future engines may include:
- AEC engine
- Finance engine
- Document engine
- AI analysis engine

All engines must follow the same platform rules.

## Summary

The developer guide defines how to build engines and handlers for the 0luka platform.

Developers must ensure:
- runtime compatibility
- artifact integrity
- deterministic execution
- platform invariant compliance

By following this guide, new engines can extend the platform safely.
