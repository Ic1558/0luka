# ADR-002: Artifact Truth Path

## Status

Accepted

## Context

In many workflow systems, outputs are loosely tracked.

This leads to problems:
- artifacts difficult to trace
- inconsistent output locations
- missing provenance

For a deterministic runtime platform, outputs must be traceable.

## Decision

0luka introduces an artifact truth system.

Artifacts must follow this pipeline:

```text
handler
 ↓
runtime state sidecar
 ↓
artifact storage
 ↓
projection
 ↓
Mission Control
```

Artifact references are recorded in runtime state.

Artifacts must be:
- immutable
- traceable to `run_id`
- generated only by handlers

## Consequences

Benefits:
- artifact provenance
- deterministic outputs
- clear audit trail

Trade-offs:
- extra runtime storage
- artifact management complexity

## Alternatives Considered

Loose output tracking:
- Rejected because output lineage becomes unreliable and auditability degrades.
