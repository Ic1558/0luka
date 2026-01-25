# PRPS — 0luka Project Registration & Policy Spec
Version: 0.2
Status: ACTIVE
Root: $HOME/0luka
Date: 2026-01-24

## 1) Mission
0luka exists to be a clean SSOT with strict directory allowlist and zero path-based identity.

## 2) Structural Law — Root Allowlist (HARD)
Only these directories may exist at $ROOT level:

- `core/` - **RIGID INFRASTRUCTURE** (Laws, PRPS, Kernel, DOE)
- `runtime/` - Active execution (Agents, Services, MCP)
- `ops/` - Tools, Gates, Scripts
- `observability/` - Logs, Reports, Evidence

**Gate enforcement**: `ops/governance/gates/00_root_allowlist_check`

## 3) Core Architecture (Rigid Backend)

Core is the **immutable foundation** that all services depend on.
It must be stable before any runtime service can function.

```
core/
├── governance/     # Laws, PRPS, Policies
├── kernel/         # Core infrastructure modules
├── doe/            # Delegation of Execution
│   ├── compiler/   # Spec → Executable
│   ├── orchestrator/
│   └── execution/
├── policies/       # Runtime policies
├── config/         # Core configuration
└── architecture.md # System architecture
```

### Core Principles:
1. **Immutability** - Core changes require explicit governance approval
2. **Dependency** - All runtime services MUST reference core, never bypass
3. **Versioning** - Core changes are versioned and traceable
4. **Plugin-Ready** - Core provides hooks for future expansion

## 4) Governance Taxonomy
- Law (docs/specs/policies) => `core/governance/`
- Police (gates/scripts/tools) => `ops/governance/`
- Evidence (logs/reports/audit) => `observability/`
- Execution (agents/services) => `runtime/`

## 5) Non-Goals (Explicit bans)
- No `g/` at root
- No legacy shim loops
- No path-based identity
- No direct file access bypassing core APIs

## 6) Enforcement
This PRPS is enforced by:
- `ops/governance/gates/00_root_allowlist_check` - Structure enforcement
- Future: `ops/governance/gates/01_core_integrity_check` - Core immutability
