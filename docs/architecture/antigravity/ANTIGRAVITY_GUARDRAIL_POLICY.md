# Antigravity Guardrail Policy

## Purpose

Antigravity runtime architecture is ratified. Changes to its contract,
classification model, and recovery interpretation must be governance-controlled
and reviewable.

## Protected Documents

- `antigravity/ANTIGRAVITY_ARCHITECTURE_CONTRACT.md`
- `antigravity/ANTIGRAVITY_DRIFT_CLASSIFICATION.md`
- `antigravity/ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md`
- `adr/ADR-AG-001-antigravity-canonical-runtime.md`

## Guardrail Rules

1. Changes to protected Antigravity docs require ADR-aware architecture review.
2. Canonical runtime ownership language must not change without ADR amendment
   or a new ADR.
3. Broker auth interpretation must remain separate from runtime and history
   interpretation.
4. UI visibility language must not imply data loss without evidence.
5. Supervisor changes must not be treated as architecture truth unless contract
   documents are updated.

## Enforcement Model

Enforcement occurs through:

- `tools/architecture_guard.sh`
- architecture compliance CI workflow
- architecture review during PR evaluation

## Non-goals

- This policy does not enforce runtime behavior directly.
- This policy does not restart or modify services.
- This policy does not validate credentials.
