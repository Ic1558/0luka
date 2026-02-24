# Implementation Plan - Pack 9: Sovereign Control Plane v1

Establish a controlled, auditable, and rate-limited runtime loop for the Sovereign OS.

## 1. Specifications & Hard Gates

- **9A: Deterministic Scheduler**
  - `tools/ops/sovereign_loop.py`: Canonical entry point.
  - `launchd/com.0luka.sovereign-loop.plist`: Cadence-driven execution.
  - `sovereign_tick`: Mandatory heartbeat in activity feed with policy/engine SHAs.
- **9B: Anti-Storm & Backoff**
  - `core/governance/sovereign_loop_policy.yaml`: Defines `min_interval_seconds` and `max_actions_per_hour`.
  - `sovereign_rate_limited`: Event emitted when caps are hit.
- **9C: Decision Auditing**
  - `observability/artifacts/sovereign_runs/<ts>_<run_id>.json`: Detailed "Explain Decision" bundle.
- **9D: Forensic Replay**
  - `tools/ops/sovereign_replay.py`: Deterministic decision parity check for past feeds.

## 2. Proposed Changes

### New Files

- `tools/ops/sovereign_loop.py`
- `core/governance/sovereign_loop_policy.yaml`
- `tools/ops/sovereign_replay.py`
- `launchd/com.0luka.sovereign-loop.plist`

### Modified Files

- `implementation_plan.md`

## 3. Verification Plan

- **Tick Proof**: Verify `sovereign_tick` exists and includes current repository SHAs.
- **Rate Limit Proof**: Inject multiple trigger events and verify `sovereign_rate_limited` blocks excess actions.
- **Replay Proof**: Run `sovereign_replay.py` on a snapshot and compare its decisions with the recorded feed events.
- **Root Hygiene**: Ensure `git status --porcelain` remains empty (excluding the target changes).
