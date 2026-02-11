---
name: verify-first
description: Run verification gates before and after code changes, prioritize health and regressions, and fail closed on missing evidence. Mandatory Read: YES
---

# Verify First

Mandatory Read: YES

## Workflow
1. Capture baseline verify results.
2. Apply minimal changes.
3. Re-run targeted and system-level verify commands.
4. Report explicit pass/fail evidence.

## Caps
- Run deterministic verification commands.
- Compare before/after outcomes.
- Block claims without proof logs.

## Forbidden
- Shipping without verification output.
- Suppressing failing checks.
- Treating flaky unrelated failures as fixed.
