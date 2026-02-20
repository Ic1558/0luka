# Workstream: B2 - Feed Immutability (04_B2)

## 1. Goal

Harden the activity feed logs against modification or deletion to ensure a reliable audit trail.

## 2. Policy/DoD

- Feed logs must be append-only.
- Proof packs must contain a hash of the current feed tail.

## 3. Steps

- Implement file-lock or shadowing of `dispatcher.jsonl`.
- Automated hash check in `save_now.zsh`.

## 4. Verify

- Attempted manual edit of log -> Alarm/Rejection.

## 5. Evidence

- [To be generated in Phase 3F]
