# Phase I: Final Handover Statement (v0.4.1)

The **0luka Governance System v0.4.1** is hereby **HANDED OVER**.

### Release Anchor (Git Sealed)
- **Tag**: `v0.4.1`
- **Commit**: `6b32428`
- **Tag Resolution**: `v0.4.1` resolves to `6b32428`. The certification decision is evaluated ONLY against this sealed baseline.
- **Non-Authoritative State**: Any post-run working-tree state (e.g., HEAD `e586bf1`) is **non-authoritative** to the certification decision.
- **Snapshot Disclaimer**: The ATG snapshot is informational only and is not used to override the sealed baseline.

### Acceptance Conditions (Verified True)
1. **Golden Script**: `ops/governance/handover_v041.zsh` completes **Start → Verify → Audit → Stop** successfully.
2. **Verification**: `ops/governance/verify_v041.py` returns **PASS**.
3. **Runtime Log Hygiene (Bounded)**: Within the certification window (**2026-01-24T21:47:00Z** <-> **21:47:03Z**), **no recurring `JSONDecodeError` loop** is observed for `gate_runnerd`. Events/logs outside this window (including isolated errors) are explicitly **out of scope** for this certification decision.

### Scope Certified
`ops/governance/gate_runnerd.py` (Judicial Daemon) is certified for non-bypassable governance, including:
- **Owner-only connections** (macOS `getpeereid` + `ctypes` fallback).
- **4-byte big-endian framing** + **1MB cap**.
- **Startup sealing** of handlers & policy.
- **Forensics chained** into `observability/stl/ledger/global_beacon.jsonl`.

### Explicitly Not in Scope (Operational Residuals Allowed)
The following legacy/experimental components are not part of the v0.4.1 certification scope. Residual callers may exist; their failure mode (ENOENT / missing artifacts) does not affect the v0.4.1 sealed governance decision:
- **Legacy bridge daemons** (e.g., `clc_wo_bridge_daemon.py`)
- **Experimental watchers** (e.g., `deploy_expense_pages_watch.zsh`)
- **MCP memory server / mcp-memory package**

### Maintenance Mode
This repo is in **Maintenance Mode** for the v0.4.1 certification scope. No **governance-certification-impacting** changes occur without a new Governance Request and a new sealed tag.

### Acceptance
**Accepted by**: icmini (USER)  
**Date**: 2026-01-25
