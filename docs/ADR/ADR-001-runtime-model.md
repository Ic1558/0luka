# ADR-001: Deterministic Runtime Execution Model

## Status

Accepted

## Context

0luka is designed as a runtime platform that executes domain workloads.

A key architectural decision was whether execution should be:
1. direct application calls
2. workflow orchestration
3. controlled runtime pipeline

Direct execution allows faster development but introduces risks:
- inconsistent execution paths
- lack of auditability
- uncontrolled side effects

For a system intended to be deterministic and auditable, execution must follow a controlled path.

## Decision

0luka adopts a deterministic runtime execution pipeline.

All workloads must follow the same execution path:

```text
Task Ingress
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
Operator Visibility
```

Execution outside this path is forbidden.

## Consequences

Benefits:
- deterministic execution
- auditability
- consistent artifact generation
- clear execution lifecycle

Trade-offs:
- increased architectural complexity
- higher implementation overhead

However, these trade-offs are acceptable for a platform-level runtime system.

## Alternatives Considered

Direct handler execution:
- Rejected because no runtime audit trail, no execution control, and weak invariant enforcement.

DAG workflow engines:
- Considered but rejected because too general and not focused on deterministic artifact generation.
