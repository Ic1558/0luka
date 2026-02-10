# Phase 15 Spec: Skill OS (Knowledge Reuse, OS-grade)

## Objective
Establish a core-brain-owned Skill OS layer that enforces deterministic knowledge reuse without execution authority.

## Scope
- Skill root SOT at `skills/manifest.md`.
- Three initial skills:
  - `notebooklm_grounding`
  - `knowledge_recycling`
  - `asset_fragment_manager`
- Advisory outputs only.

## Invariants
- Phase 15 is learning without execution.
- No dispatcher, router, or policy auto-apply.
- No dependency on Antigravity runtime.
- Read/assist only, fail-closed on missing manifest contract.

## Inputs
- Observability logs and verification artifacts.
- Existing lesson files and safe utility fragments.

## Outputs
- Advisory lesson markdown in `observability/lessons/`.
- Reuse guidance references for future planning.

## Non-Goals
- Kernel refactor.
- Execution logic changes.
- Auto-learning mutation.
