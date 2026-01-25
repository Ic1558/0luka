# Governance Request: GR-001 (Upgrade to v0.5.0)

**Target Version**: v0.5.0
**Requester**: Antigravity (Agent)
**Date**: 2026-01-26

## Motivation
The implementation of **MCP Hand v1.0** requires a centralized authorization step (`authorize`) to enforce allowed actions before execution. The current **v0.4.1 Sealed Daemon** does not support this command, causing `mcp_exec.py` to fail secure verification.

## Proposed Changes
1.  **Unseal `ops/governance/gate_runnerd.py`**:
    *   Implement `authorize(action, args)` method.
    *   Validate action against `ontology.yaml` or internal `ACTION_TABLE`.
    *   Return `{"ok": True/False, "allowed": True/False}`.

2.  **Update `core/governance/ontology.yaml`**:
    *   Define the allowed MCP actions (`action.followup.generate`, `action.ram.snapshot`, `action.mls.watch`).

3.  **Reseal as v0.5.0**:
    *   Update `Handover_OnePager.md`.
    *   Tag `v0.5.0`.

## Verification Plan
1.  **Hand Loop Test**: `test_hand_followup.json` -> `mcp_exec.py` -> `gate_runnerd` -> OK.
2.  **Forensics**: Verify `authorize` call is logged in `global_beacon.jsonl` (as `run_gates` or similar event) or just `audit`.
