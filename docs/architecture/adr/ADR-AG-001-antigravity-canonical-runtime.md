ADR-ID: ADR-AG-001
Title: Antigravity Canonical Runtime Contract
Status: Accepted
Date: 2026-03-13
Owner: 0luka Architecture Authority
Supersedes: None
Related:
- ANTIGRAVITY_ARCHITECTURE_CONTRACT.md
- ANTIGRAVITY_DRIFT_CLASSIFICATION.md
- ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md

## Context

Antigravity runtime incidents produced ambiguity across runtime supervision,
entrypoint path resolution, broker authentication boundary, and UI visibility.
This ADR clarifies the canonical runtime contract and binds interpretation to
governance artifacts rather than transient runtime symptoms.

## Decision

0luka adopts the following documents as canonical Antigravity runtime
governance:

- `ANTIGRAVITY_ARCHITECTURE_CONTRACT.md`
- `ANTIGRAVITY_DRIFT_CLASSIFICATION.md`
- `ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md`

These documents define runtime ownership, drift interpretation, and recovery
procedures.

## Consequences

Positive:

- deterministic runtime interpretation
- incident classification model
- operational recovery clarity

Constraints:

- broker auth failures must not be interpreted as runtime failure
- UI visibility issues must not imply data loss

## Incident Record

Resolved architecture incident classification:

Architecture Drift + Credential Pairing Mismatch

Tracks:

Track A: Closed
Track B: Closed
Track C: Open

Historical runtime data loss: Not observed.

## Change Control

Future changes to this decision require ADR amendment.
