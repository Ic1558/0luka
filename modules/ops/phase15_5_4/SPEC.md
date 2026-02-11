# Phase 15.5.4 Specification - Operational Proof Mode

## Objective
Promote `PHASE_15_5_3` proof from synthetic to operational by making `tools/ops/idle_drift_monitor.py` the runtime truth source for activity chain emission.

## Source of Truth
- Activity feed resolution order:
  1. `LUKA_ACTIVITY_FEED_JSONL`
  2. `observability/logs/activity_feed.jsonl`
- Operational event emitter: `tools/ops/idle_drift_monitor.py`
- Checker enforcement: `tools/ops/dod_checker.py`

## Required Runtime Events
For each `--once` run (non-fatal path), monitor appends:
- `started`
- `completed`
- `verified`

Each event includes:
- `phase_id=PHASE_15_5_3`
- `emit_mode=runtime_auto`
- `verifier_mode=operational_proof`
- `tool=idle_drift_monitor`
- `run_id`
- `ts_epoch_ms`
- `ts_utc`

`completed` and `verified` include evidence path references to idle/drift artifacts.

## Checker Enforcement
When `LUKA_REQUIRE_OPERATIONAL_PROOF=1` for `PHASE_15_5_3`:
- non-runtime chain => `proof.synthetic_not_allowed`
- missing taxonomy keys => `taxonomy.incomplete_event`
- malformed activity feed => exit code `4`

Exit semantics remain `0/2/3/4`.
