# Boss AI Development Policy

## Rule 1 — Fail-Closed by Default
If preconditions are unknown or validation fails, stop execution and surface evidence instead of guessing.

## Rule 2 — Evidence Before Claims
Any technical claim must be supported by reproducible command output, test result, or artifact path.

## Rule 3 — Source Of Truth Discipline
Canonical law lives in `core/governance/`; `core_brain` is an interpretation and execution layer only.

## Rule 4 — No Hidden Mutation
Changes to governance-critical files require explicit review intent (`governance-change`) and traceable manifests.

## Rule 5 — Non-Destructive Operations
Never run destructive or history-rewriting actions without explicit approval and a recovery snapshot.
