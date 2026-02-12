# Decision: Universal Auto-Adaptive Governor Router

**Decision ID**: `AUTO_ADAPTIVE_GOVERNOR_20260213`
**Date**: 2026-02-13
**Status**: Approved (Universal Mode)
**Owner**: GMX (System Sovereign)
**Scope**: 0luka repository (Tool-Agnostic)

---

## Context

Governance previously relied on agent discipline or IDE-specific prompts. This led to:
- Inconsistent enforcement across tools (Antigravity vs Windsurf)
- Manual burden to select "strict" vs "rapid" modes
- Risk of governance drift in non-standard environments

## Decision

Implement a **Universal, Tool-Agnostic Auto-Adaptive Governor Router** enforced via:
1. **Contract**: `core/governance/auto_governor_contract.yaml` (Single Source of Truth)
2. **Router CLI**: `tools/ops/auto_governor_router.py` (Standard Execution)
3. **CI Binding**: `.github/workflows/governor-router.yml` (Mandatory Check)

### Core Logic (The "Rings")

| Ring | Path Scope | Risk | Mode | Requirements |
|---|---|---|---|---|
| **R3** (Critical) | `core/`, `.github/`, contracts | Critical | **HARD** | Tests, Invariants, Rollback Plan, `governance-change` label |
| **R2** (Ops) | `core_brain/`, `tools/ops/` | High | **MED** | Structured Plan, Implementation Steps |
| **R1** (Modules) | `modules/`, `skills/` | Medium | **MED** | Scope & Deps, Expected Results |
| **R0** (Artifacts) | `docs/`, `logs/`, `observability/` | Low | **SOFT** | Traceability only (commit msg) |

### Universal Enforcement
- **Inputs**: Natural Language OR File Paths
- **Outputs**: JSON Plan + Exit Code
- **Fail-Closed**: Unknown scope = Exit 4 (blocks execution)

## Impact
- **All Agents/Tools** (Antigravity, Windsurf, Codex CLI) MUST invoke the router before planning.
- **CI** blocks PRs that touch R3 files without proper labeling.
- **Zero Governance Drift**: Governance rules are code (`.yaml`), not prompt text.

## Success Metrics
- 100% of R3 changes pass through router in CI
- Zero "unknown scope" commits to `main`
- Router latency < 200ms

## References
- Contract: `core/governance/auto_governor_contract.yaml`
- Router: `tools/ops/auto_governor_router.py`
- Tests: `core/verify/test_auto_governor_router.py`
