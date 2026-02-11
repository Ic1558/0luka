---
name: single-flight
description: Enforce single-flight/no-retry execution discipline to avoid duplicate runs and retry storms. Use for CI/API-sensitive operations and governance-critical flows. Mandatory Read: YES
---

# Single Flight

Mandatory Read: YES

## Workflow
1. Execute one in-flight operation at a time.
2. Set retries to zero unless explicitly overridden.
3. Reject parallel fan-out for guarded operations.
4. Emit clear status for wait/skip/fail decisions.

## Caps
- Apply deterministic retry/no-parallel policy.
- Prevent duplicate execution attempts.
- Keep operation ordering stable.

## Forbidden
- Blind retries.
- Parallel execution on guarded paths.
- Hidden backoff loops.
