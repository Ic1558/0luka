---
name: scope-lock
description: Enforce strict task boundaries, prevent scope creep, and block unrelated edits. Use for PR-safe implementation where only declared files/modules are allowed. Mandatory Read: YES
---

# Scope Lock

Mandatory Read: YES

## Workflow
1. Read declared scope and non-goals.
2. Build a file allowlist before editing.
3. Reject edits outside allowlist with explicit why-not.
4. Verify changed-files set matches scope.

## Caps
- Analyze diffs against declared scope.
- Enforce fail-closed on scope violations.
- Produce scope compliance notes.

## Forbidden
- Expanding scope without explicit approval.
- Touching unrelated modules.
- Silent edits outside allowlist.
