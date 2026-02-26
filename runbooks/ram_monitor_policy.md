# RAM Monitor Policy (Composite + Hysteresis)

## Purpose
`tools/ram_monitor.zsh` uses a composite decision model to reduce false `CRITICAL` on macOS where `Pages free` can be low while `memory_pressure` is still operational.

## Inputs
- `base_pressure_level` from `memory_pressure -Q` free percentage
- `free_bytes` from `vm_stat`
- `compressed_bytes` from `vm_stat`
- `swapins/swapouts` deltas (when available)

## Decision Model
- `low_free`: `free_bytes < RAM_MON_FREE_CRIT_BYTES` (default `200MB`)
- `high_compressed`: `compressed_bytes >= RAM_MON_COMPRESSED_CRIT_BYTES` (default `6GB`)
- `high_swap_activity`: swap deltas above `RAM_MON_SWAP_DELTA_CRIT` (default `1`) when swap metrics are available
- Composite critical:
  - `CRITICAL` only when `base_pressure_level == CRITICAL` and `(low_free OR high_compressed OR high_swap_activity)`
- Non-critical:
  - `WARN` when base is `WARN` or compression is high
  - `OK` otherwise

Rationale: `Pages free` alone can be conservative on macOS; composite gates avoid over-triggering from a single metric.

## Hysteresis Latch Clear
- `RAM_MON_CLEAR_STREAK` (default `3`) defines consecutive non-CRITICAL samples required to clear latch.
- State fields:
  - `non_critical_streak`
  - `latch_active`
  - `critical_since_epoch`
- Behavior:
  - On `CRITICAL`: streak resets to `0`, latch set active.
  - On non-CRITICAL: streak increments.
  - Clear occurs only when streak `>= RAM_MON_CLEAR_STREAK`.

## Operational Verification (DoD)
```bash
cd /Users/icmini/0luka
zsh -n tools/ram_monitor.zsh
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime ./tools/ram_monitor.zsh --once
tail -n 80 /Users/icmini/0luka/observability/telemetry/ram_monitor.state.json
tail -n 120 /Users/icmini/0luka/observability/telemetry/ram_monitor.latest.json
```

Aligned outcome:
- `latch_active=false`
- `critical_since_epoch=null`
- `non_critical_streak >= clear_streak_required`
- `decision.composite_critical=false` unless base pressure is truly critical with stress flags

## Drift Interpretation
- `SOFT DRIFT`: policy mismatch/signals disagree while contracts still hold.
- `CONTRACT DRIFT`: schema/path/event contract is violated.

Evidence paths:
- `/Users/icmini/0luka/observability/telemetry/ram_monitor.latest.json`
- `/Users/icmini/0luka/observability/telemetry/ram_monitor.state.json`
- `/Users/icmini/0luka/observability/logs/components/ram_monitor.jsonl`

## Rollback (Docs)
If policy must be reverted, revert merge commit from PR #148:

```bash
cd /Users/icmini/0luka
git revert 16d8e01
```

Do not execute rollback during freeze without governance approval.
