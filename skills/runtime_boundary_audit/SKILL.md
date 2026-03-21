---
name: runtime_boundary_audit
description: Audit runtime boundary integrity for LUKA runtime roots and related environment-boundary invariants. Use for governed read-only boundary checks and fail-closed audit planning. Mandatory Read: YES
---

# Runtime Boundary Audit

Mandatory Read: YES

## Workflow
1. Read declared runtime-boundary scope and target runtime-root context.
2. Inspect only the declared boundary inputs and invariants.
3. Produce a read-only boundary status with explicit findings.
4. Fail closed when boundary evidence is missing or ambiguous.

## Inputs
- Declared runtime-root or boundary target
- Boundary-relevant environment or path evidence
- Verification context for the current bounded task

## Outputs
- Boundary status summary
- Explicit findings list
- Next-check recommendation

## Caps
- Read-only runtime-boundary inspection
- Deterministic audit summary generation
- Fail-closed reporting on missing evidence

## Forbidden
- Mutating runtime state
- Remediating environment configuration
- Expanding into scheduler, policy, or deployment changes
