# 0luka — Human Dashboard (30s)

> This file is the single quickest way for humans to understand system state.
> Keep it short. No specs. No essays.

## Mode
- **mode:** Phase-O (Core-Operability Finalization)
- **core-contract:** CLOSED (do not modify SOT/governance/semantics/routing)

## What matters right now
- **Today’s focus:** Scaffolding + minimal Log Rotation + Summary
- **Done when:**
  - paths are stable + referenced consistently
  - logs don’t grow forever and are auditable
  - summary answers: “what is happening now?”

## Canonical paths
- `./core/` — core logic (contract locked)
- `./state/` — current system state snapshots (small, structured)
- `./logs/` — runtime logs (rotated, auditable)
- `./reports/` — human-readable reports & summaries
- `./memory/` — durable notes / lessons / references
- `./artifacts/` — tasks/runs/evidence (system outputs)

## Quick commands
- View summary: `cat reports/summary/latest.md`
- Tail key logs:
  - `tail -n 50 logs/components/bridge/current.log`
  - `tail -n 50 logs/components/watchdog/current.log`

## Pending
- [ ] Validate log rotation is working daily
- [ ] Ensure summary runs without errors

<!-- PHASE_O_POINTERS -->
## Phase-O Pointers (core-operability)
- Human Dashboard: `luka.md`
- Machine State: `state/current_system.json`, `state/pending.yaml`, `state/recent_changes.jsonl`
- Observability Telemetry: `observability/telemetry/*.latest.json`
- Component Logs (standardized): `logs/components/<component>/current.log`
- Summary Latest: `reports/summary/latest.md`

