# Antigravity Runtime Services (Scaffold)

This directory defines a unified runtime service contract for Antigravity.

## Purpose

- provide one interface surface for executor, worker, and artifact engine
- standardize request and result structures for runtime service calls
- prepare unification without changing existing runtime behavior

## Integration Direction

- `executor_adapter.py` wraps `AntigravityRuntimeExecutor`
- `worker_adapter.py` wraps `AntigravityRuntimeWorker`
- `artifact_engine_adapter.py` wraps `ArtifactEngine`

## Scope Boundary

- scaffold-only for this phase
- no PM2 or launchd logic
- no broker or external API logic
- no runtime mutation and no behavior change
- registry is in-memory only
