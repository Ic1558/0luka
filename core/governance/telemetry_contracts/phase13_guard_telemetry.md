# PHASE13B Guard Telemetry Contract

## Purpose
Defines the telemetry contract for dispatcher boundary guard blocked events emitted with `phase_id=PHASE13B_GUARD_TELEMETRY`.

## Required Fields
Each guard telemetry event must include:
- `ts_utc`
- `run_id`
- `task_id` (if available)
- `phase_id` (must be `PHASE13B_GUARD_TELEMETRY`)
- `action` (must be `blocked`)
- `reason_code` (short enum string)
- `missing_fields` (array of field names)
- `root_kind` (`template|relative|absolute|empty`)
- `payload_sha256_8` (8-char prefix from canonicalized payload hash)

## Privacy Invariants
- Never emit raw `root` value in telemetry.
- Never emit raw payload fragments in telemetry.
- Use hash-only payload identity via `payload_sha256_8`.

## Counters Mapping
Dispatcher runtime stats maintain aggregated counters:
- `total_guard_blocked`
- `total_malformed`
- `total_guard_blocked_by_reason.<reason_code>`

## Reason Code Guidance
Examples:
- `SCHEMA_VALIDATION_FAILED`
- `MISSING_REQUIRED_FIELDS`
- `ROOT_ABSOLUTE`
- `INVALID_OPS`
- `MALFORMED_TASK`
