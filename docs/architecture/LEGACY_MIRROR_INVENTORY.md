# Legacy Mirror Inventory

## Purpose

Legacy top-level result fields still exist for compatibility with older readers and outer-envelope tooling. After AG-17 closure, `ExecutionEnvelope` is the canonical execution authority surface, so remaining direct reads of top-level result mirrors are now architectural debt that must be inventoried before retirement work begins.

## AG-17 reference

AG-17 closed under Decision B semantics: embedded and top-level `outputs_sha256` hashes represent different integrity scopes and are not required to match. AG-17 closed by semantic clarification, not runtime redesign. The closeout evidence pack remains under `evidence/ag17/`.

## Mirror fields

Primary current mirror fields:

- `status`
- `summary`
- `provenance`
- `seal`
- evidence-derived execution events

Historical or partial authority fields still relevant to retirement planning:

- `executor`
- `routing`
- `policy`

These fields appear either as direct top-level reads or as emitter/normalizer dependencies that still reason about top-level result envelopes outside `core.result_reader`.

## Inventory results

### Category A — canonical readers

These files already use `core.result_reader` and are safe for envelope-first authority:

- `core/health.py`
- `core/phase1d_result_gate.py`
- `core/verify/test_phase15_5_2_timeline_heartbeat.py`
- `core/verify/test_phase8_dispatcher.py`
- `core/verify/test_result_reader.py`
- `core/verify/test_task_dispatcher.py`

### Category B — mirror dependencies

These files still read top-level result-envelope fields directly and therefore remain legacy mirror dependencies:

- `core/outbox_writer.py:102,112,116` — reads top-level `summary` and `provenance.hashes` while constructing the outer persisted result envelope.
- `core/cli.py:169` — checks top-level dispatch `status` directly for CLI exit behavior.
- `core/circuit_breaker.py:72` — treats top-level `status == "error"` as a generic failure signal.
- `core/task_dispatcher.py:1170,1179,1362,1367` — reads top-level dispatch/audit statuses directly in dispatcher control flow and CLI-mode exit aggregation.
- `core/verify/test_watchdog.py:61,91` — asserts top-level watchdog result `status` directly.

### Category C — ambiguous

These files need manual review before retirement planning because it is unclear whether they are consuming result mirrors, generic status dictionaries, or unrelated telemetry payloads:

- `core/phase1a_emit.py:211,223` — reads `result.get("executor")` for telemetry/ledger export, but the source object is not clearly a canonical task result envelope.
- `core/verify/test_phase15_5_2_timeline_heartbeat.py:66,123,137` — uses `get_result_status(result) or result.get("status")`; this is helper-first and safe in practice, but the fallback keeps a legacy mirror dependency path alive.
- `core/verify/test_phase8_dispatcher.py:126` — checks `result.get("status")` on the dispatcher return object before switching to helper-based artifact reads.

## Retirement readiness summary

The repository is not ready for mirror retirement yet. Canonical reader adoption exists in the intended AG-17 surfaces, but runtime-adjacent components (`core/outbox_writer.py`, `core/task_dispatcher.py`, `core/cli.py`) still depend on top-level result fields directly. The next safe step is reader-completion plus guard preparation, not field removal.
