# Artifact Log Retention Policy (Kernel V.2)

## Scope
This policy governs kernel-generated runtime artifacts under `observability/` and `interface/` for the V.2 dispatch pipeline.

## Categories
- `observability/logs/dispatcher.jsonl`
- `observability/artifacts/router_audit/*.json`
- `interface/completed/*.yaml`
- `interface/rejected/*.yaml`

## Boundaries
- Paths are resolved from repository `ROOT` only.
- No absolute hard paths are written to retention output.
- Retention is kernel-scoped (`core/retention.py`) and does not modify `core_brain/ops/governance/retention_daemon.py`.

## Retention Rules
- Dispatcher log rotate:
  - Threshold: `>1024 KB`
  - Rotation: `.1 .. .3` (keep 3 rotated copies)
- Router audit age-out:
  - Max age: `30 days`
  - Always keep newest `50` files minimum
- Completed tasks age-out:
  - Max age: `14 days`
  - Always keep newest `20` files minimum
- Rejected tasks age-out:
  - Max age: `14 days`
  - Always keep newest `20` files minimum

## Protected Files (Never Delete)
- `observability/artifacts/dispatch_latest.json`
- `observability/artifacts/dispatch_ledger.json`
- `observability/artifacts/dispatcher_heartbeat.json`

## Activity Feed
Retention emits important delta events only to `observability/activity/activity.jsonl`:
- `retention.rotate`
- `retention.delete`
- `retention.protected_skip`
- `retention.error`

Event fields: `ts_utc`, `actor`, `type`, `severity`, `summary`, `meta{path,bytes,keep_days,dry_run}`.

## Escalation
Escalate when:
- repeated `retention.error` events appear,
- log rotation happens continuously across runs,
- protected files are missing or malformed.

## Where To Check
- Dry run: `python3 core/retention.py --dry-run --json`
- Health: `python3 core/health.py --full`
- Activity: `observability/activity/activity.jsonl`
