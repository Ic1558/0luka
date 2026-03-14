# AG-17D2 — Outputs Hash Semantics Alignment

## Decision lineage and phase boundary
- AG-17C2 remains **PASS** (no change in this slice).
- AG-17D1b resolved Decision B as final.
- AG-17D2 aligns validation, tests, and documentation to Decision B semantics.
- This slice performs **no runtime flow redesign**, **no sealing relocation**, and **no schema change**.

## Final semantics (Decision B)

### Execution-envelope outputs hash
- Field: `execution_envelope.provenance.outputs_sha256` (embedded scope semantics).
- Meaning: digest of the execution-envelope output payload at **envelope seal time**.
- Scope: execution-envelope payload only.

### Artifact/result-envelope outputs hash
- Field: `artifact.provenance.hashes.outputs_sha256` (top-level artifact scope semantics).
- Meaning: digest of the finalized result artifact `outputs` block at **outbox emission time**.
- Scope: finalized result-envelope outputs block.

## Validation semantics in AG-17D2
- Equality between embedded execution-envelope outputs hash and artifact/result-envelope outputs hash is **not required**.
- Validation should enforce:
  - embedded outputs hash is non-empty,
  - embedded outputs hash is stable for identical execution-envelope payload,
  - top-level outputs hash is non-empty,
  - top-level outputs hash validates against final artifact-scope reconstruction.

## Mismatch handling
- A difference between the two outputs hashes is **not a defect** by itself.
- Difference reflects intentionally different hash scopes across phase boundaries.
