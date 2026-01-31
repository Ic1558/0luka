# Rio Sandbox (R&D)
**"Explore, but do not touch."**

## Purpose
This directory (`sandbox/rio/`) is the designated playground for `[Rio]`, the R&D Agent. It is used for drafting RFCs, testing new prompts, and exploring non-destructive hypotheses.

## Sandbox Rules (Strict)
1.  **Isolation**: Code here MUST NOT be imported by Production systems (`tools/`, `core/`, `interface/`).
2.  **No Write Access**: Rio scripts CANNOT write to any path outside of `sandbox/rio/`.
3.  **No Production Data**: Rio CANNOT access live keys, secrets, or PII.
4.  **No Policy Logic**: This folder cannot contain governance gates or authorization logic.

## Workflow
1.  **Idea**: Rio drafts an RFC using `RFC_TEMPLATE.md`.
2.  **Review**: Liam reviews the RFC.
3.  **Promotion**: If accepted, Liam creates a `TaskSpec` to move the feature to `skills/` or `core/` via Lisa.
