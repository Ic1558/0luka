# Pack 6: Activity Feed as Canonical Runtime Bus

## Objective

To escalate `activity_feed.jsonl` from an untyped observability log to a strongly typed, fail-closed constitutional runtime contract. This enforces that the system cannot act, suffer anomalies, or maintain state without verifiable, strict correlation in the activity feed.

## Phase 1: Schema Contract (The Foundation)

**File**: `core/observability/activity_feed.schema.json`

- Define a rigid JSON schema covering:
  - Required structural fields (e.g., `ts_utc`, `action`)
  - Permitted conditional fields (e.g., `level` for RAM alerts, `lock_acquired` for maintenance).
- **Rule**: If an emitter creates structurally invalid JSON against this schema, it fails aggressively *before* the append operation.
- Emit mode enforcement to ensure all external agents explicitly define their operational mode (e.g., `runtime_auto` or `manual_invoke`).

## Phase 2: Signal Integrity (The Linter)

**Update**: `tools/ops/activity_feed_linter.py --strict`

- Extend the linter to ingest `activity_feed.schema.json` and validate the `.jsonl`.
- Add deterministic temporal/logical checks:
  - Monotonically increasing `ts_utc` (no time regressions).
  - Suppression/Alerting on duplicate ID bursts.
  - Ensuring CRITICAL memory anomalies respect explicit cooldown backoffs.
- Integrates into existing verification checks and fail-closed CI environments.

## Phase 3: Runtime Watermark Anomalies (The Guard)

**File**: `tools/ops/activity_feed_guard.py`

- Operates on the runtime data to identify signal corruption and gaps:
  - Tracks last epoch ms seen
  - Raises exception on `ts` regressions or event bursts
  - Monitors for silent gaps (e.g. heartbeat lost for >N seconds)
- Action: Emits `feed_anomaly` and routes to standard exception mechanisms (potentially interacting with CANARY).

## Phase 4: Escalation Logic Formulation (The Consequence)

- The convergence point: Correlation Detection.
  - Context: What happens if `ram_pressure_persistent == CRITICAL` AND `activity_feed_maintenance == noop`?
  - Rule: If system pressure exceeds an unresolved threshold despite scheduled automated maintenance runs, it escalates to an explicit `system_pressure_unresolved` action at `HIGH` severity.
  - This transitions the environment from "merely reporting" to "making verifiable judgments based on systemic correlation".

## Governance Gate

- Await strict user verification prior to moving from Plan -> Code -> Dry-Run -> Implementation.
