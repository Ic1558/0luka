---
name: asset_fragment_manager
description: Reuse deterministic utility fragments through import-only guidance. Use when selecting existing helpers (unit conversion, snapping, validation) without mutating fragment sources.
---

# Asset Fragment Manager

Mandatory Read: NO

## Purpose
Select and reuse deterministic utility fragments instead of rewriting them.

## Rules
- Import-only workflow.
- Keep fragment source immutable.
- Prefer smallest stable fragment with existing tests.

## Inputs
- Existing utility files under repo paths.

## Outputs
- Suggested import path(s).
- Usage snippet and constraints.

## Caps
- Search and compare candidate fragments.
- Recommend deterministic reuse path.

## Forbidden
- No fragment mutation.
- No runtime execution side effects.
- No automatic refactor across modules.
