# Cole Enablement Reconciliation Evidence Report
**Date**: 2026-02-06
**Agent**: [GMX]
**Commit**: `a1ebc5d`

## 1. Objective
Reconcile unauthorized edits by [Cole] while enabling declarative routing and mechanical safety locks for long-run orchestration.

## 2. Actions Taken

### Phase 0: Evidence Gathering
- Audited `core_brain/governance/agents.md` and `tools/bridge/consumer.py`.
- Identified unauthorized file writes and documentation gap.

### Phase 1: Rollback & Cleanup
- Restored `core_brain/governance/agents.md` to HEAD (pristine state).
- Restored `state/current_system.json` to HEAD.
- Cleaned up dangling artifacts.

### Phase 2: Additive Re-application (Controlled)
- **Bridge Hardening**: Implemented "Mechanical Mode Lock" in `tools/bridge/consumer.py`.
    - Restricted write access to `cole/` prefix by default.
    - Blocked shell redirection and restricted git subcommands in Free Mode.
    - Added `[Cole]` to `ALLOWED_CALL_SIGNS`.
- **Governance Updates**: 
    - Updated `core_brain/governance/router.md` to route `LONG_RUN / ORCHESTRATE` to `[Cole]`.
    - Updated `0luka.md` to reflect `[Cole]` as a Core Actor (Hybrid Helper).
- **Migration**: Moved legacy Opencode artifacts to `cole/_legacy/`.

## 3. Verification Evidence
- **Core Integrity**: `verify-core` command returned `OK`.
- **Identity Enforcement**: Cole is recognized as a valid caller but locked to its designated sandbox.
- **Traceability**: All changes reviewed and approved before final commit.

---
*End of Report*
