# ADR-005: Runtime Integrity Protection

## Status

Accepted

## Context

Runtime systems may experience anomalies:
- invalid state transitions
- missing artifacts
- projection drift
- dispatcher failure

Manual detection is unreliable.

## Decision

The platform introduces two protection layers:

Runtime Validator:
- detects invariant violations.

Runtime Guardian:
- performs automatic recovery.

Protection chain:

```text
Kernel Invariants
 ↓
State Machine
 ↓
Runtime Validator
 ↓
Runtime Guardian
```

## Consequences

Benefits:
- automatic anomaly detection
- self-healing runtime
- improved platform stability

Trade-offs:
- additional system complexity

## Alternatives Considered

Operator-only monitoring:
- Rejected because detection latency and consistency are insufficient for runtime safety requirements.
