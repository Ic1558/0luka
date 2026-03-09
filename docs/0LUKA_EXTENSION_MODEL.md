# 0LUKA Extension Model

Version: `v1.0`  
Status: `Platform Extension Specification`

## 1. Purpose

This document defines how domain engines extend the 0luka runtime platform.

The extension model ensures that:
- new engines integrate safely
- runtime invariants remain protected
- execution remains deterministic
- artifact provenance is preserved

This model allows the platform to grow while keeping the runtime kernel stable.

## 2. Extension Philosophy

0luka is designed as a runtime platform, not a monolithic application.

Therefore:
- core runtime = stable kernel
- domain engines = pluggable modules

All domain engines must integrate through the runtime execution contract.

## 3. Extension Boundary

Domain engines must never bypass runtime control.

Required execution path:

```text
dispatcher
 → router
 → runtime state
 → approval gate
 → execution adapter
 → domain handler
```

Direct execution is forbidden.

## 4. Engine Structure

Each engine resides under:

`repos/<engine_name>/`

Example:

```text
repos/
   qs/
   aec/
   finance/
   document/
```

Typical engine structure:

```text
repos/qs/
   src/
      engine/
         job_registry.py
         handlers/
            boq_extract.py
            cost_estimate.py
            po_generate.py
            report_generate.py
   tests/
```

## 5. Engine Registration

Engines must register job types using a deterministic registry.

Example:

`job_type → handler`

Example registry:
- `qs.boq_extract`
- `qs.cost_estimate`
- `qs.po_generate`
- `qs.report_generate`

Unknown jobs must fail closed.

## 6. Execution Interface

All engines must implement the runtime contract.

`run_registered_job(job_type, context)`

Context fields:
- `run_id`
- `job_type`
- `project_id`
- `metadata`

Return format:
- `artifact_refs`

Handlers must never fabricate artifacts.

## 7. Approval Integration

If a job requires approval:

`execution_status = blocked`

Execution must only begin after approval.

`pending_approval → approved`

Approval bypass is prohibited.

## 8. Runtime Invariant Compliance

All engines must obey runtime invariants defined in:

- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_RUNTIME_INVARIANTS.md`

Examples:
- deterministic execution
- fail-closed behavior
- artifact provenance integrity

## 9. Engine Isolation

Engines must not modify:
- runtime kernel
- dispatcher logic
- state machine
- approval system

Engines only provide:
- domain logic
- artifact generation
- domain validation

## 10. Artifact Responsibility

Handlers must generate artifacts through the artifact contract.

`artifact_refs`

Artifact structure defined in:

- `docs/0LUKA_ARTIFACT_MODEL.md`

Artifacts must remain immutable.

## 11. Adding a New Engine

Example: AEC engine.

Directory:

`repos/aec/`

Handlers:
- `aec.drawing_parse`
- `aec.model_generate`
- `aec.material_quantify`
- `aec.render_report`

Execution still uses:

`run_registered_job()`

Runtime behavior remains unchanged.

## 12. Platform Stability Rule

The extension model ensures:
- core runtime evolves slowly
- domain engines evolve independently

This prevents platform instability.

## Summary

The extension model allows the 0luka platform to grow by adding domain engines without modifying the runtime kernel.

Engines must integrate through the runtime contract while preserving:
- deterministic execution
- artifact provenance
- runtime invariants
