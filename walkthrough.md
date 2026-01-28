# Walkthrough: Establish Liam Planner & Bridge Integration

**Status:** ✅ COMPLETE
**Date:** 2026-01-28

## Goal
Integrate **Liam Planner (Reasoning Agent)** and **Codex (Verification Agent)** with the **0luka Bridge** to enable automated Planning and Verification loops triggered by the system.

## Accomplishments

### 1. Phase 2: Bridge Intent `plan` (Liam Integration)
- **Routing**: Configured `bridge_dispatcher` to route `intent: plan` -> `action.plan`.
- **Governance**: Added `action.plan` to `gate_runnerd` allowlist (executing `system/bin/liam-planner`).
- **Dynamic Goal**: Updated `liam_planner.py` to accept `LUKA_ARGS_JSON` environment variable, allowing the Bridge to inject dynamic goals.

### 2. Phase 2.1: Real Goal Trial (Validation)
- **Test**: Emitted task `{"goal": "Check Port 7001 occupancy"}`.
- **Trace**:
    1.  `bridge-emit` -> Inbox.
    2.  `bridge-dispatcher` -> `gate_runnerd` (RPC).
    3.  `gate_runnerd` -> `liam_planner.py` (Shim).
    4.  `liam_planner` -> `trace-unknown.plan.json`.
- **Result**: Plan artifact correctly reflected the injected goal, proving the "Auto-Flow" chain.

### 3. Phase 2.2: Verifier Hook (Codex Integration)
- **Goal**: Enable "Verification" capability in the Identity Service.
- **Implementation**:
    - Created `core_brain/ops/governance/codex_verifier.py` (Secure Adapter).
        - **Security**: Strict allowlist (`ls`, `grep`, `curl`, `ps`, etc.).
        - **Robustness**: Handles double-encoded JSON payloads.
    - Added `codex` to `registry.yaml` with `[verify]` capability.
    - Wired `intent: verify` -> `action.verify` in Dispatcher and Gate Runner.
- **Validation**:
    - Emitted `verify` task: `{"check": "ls -F"}`.
    - **Result**: `dispatcher_verify.log` confirmed `SUCCESS` with directory listing.

## Proof of Function
The "Trinity" Loop is now technically possible:
1.  **Plan**: `bridge-emit plan '{"goal": "..."}'` -> Liam generates Plan.
2.  **Execute**: (Human/Lisa) executes plan.
3.  **Verify**: `bridge-emit verify '{"check": "..."}'` -> Codex verifies result.

## Artifacts Created
- `core_brain/ops/governance/bridge_dispatcher.py` (The Router)
- `core_brain/ops/governance/codex_verifier.py` (The Verifier)
- `system/planners/liam_planner.py` (The Planner - Enhanced)

## Next Steps
- **Operationalize**: The system is now ready for "Phase 3: Autonomous Loops" (if desired), where the system self-emits verification tasks.
- **Cleanup**: `bridge_dispatcher.py` is currently a one-shot script. For production self-healing, it should be daemonized.
