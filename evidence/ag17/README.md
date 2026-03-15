# AG-17 Closeout Evidence

- Artifact path: `/Users/icmini/0luka/interface/outbox/tasks/ag17-closeout-proof-001.result.json`
- Embedded outputs hash: `09ddbe3722769c3116595547b066755590ebeda5203a00fa7835209ecf9a03bc`
- Top-level outputs hash: `9b98cdff8cf1c3eb4d48e87e8aaa3b1bd3696c6c0f9967a36d4ac4cb037a054f`
- Equal: `False`

## Code-path interpretation

- `core.task_dispatcher._build_result_bundle()` precomputes `result_bundle["provenance"]["hashes"]["outputs_sha256"]` from the result bundle outputs/artifacts payload before `_attach_execution_envelope()` seals the embedded envelope.
- `core.outbox_writer.write_result_to_outbox()` later recomputes top-level `provenance.hashes.outputs_sha256` by hashing the normalized outer result envelope with `outputs_sha256` blanked and `seal` removed.

Under current runtime code, these hashes come from different scopes. Equality is not a current runtime invariant.
