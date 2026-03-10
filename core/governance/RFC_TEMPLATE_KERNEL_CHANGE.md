# RFC — Kernel Core Change

## 1. Problem Statement

Describe the deterministic issue or requirement.

## 2. Determinism Impact

Does this alter:

- lifecycle ordering?
- submit-time validation?
- runtime prerequisite semantics?
- quarantine behavior?
If yes, explain precisely.

## 3. Contract Impact Analysis

Which section of kernel_frozen_manifest.yaml is affected?

## 4. Proposed Change

Exact semantic change.

## 5. Safety Guarantees

- Will SOT remain append-only?
- Will lifecycle ordering remain valid?
- Will linter invariant remain unchanged?

## 6. Proof Requirements

Must include:

- watch-lane execution proof
- pytest PASS
- linter PASS (ok=true, violations=0)
- proof pack reference

## 7. Rollback Plan

Describe deterministic rollback.
