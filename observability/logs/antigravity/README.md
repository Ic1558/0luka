# Antigravity Observability Ownership

Antigravity runtime logs and audit outputs are anchored under 0luka
observability ownership.

## Ownership Rule

- `observability/logs/antigravity/` is the canonical observability namespace
  for Antigravity runtime logging ownership.
- app-local logs may still exist during migration, but they are not the final
  source-of-truth ownership boundary.

## Intended Uses

- runtime service logs
- deploy/bootstrap evidence
- PM2/service supervision evidence
- bounded audit summaries

## Phase A.2 Normalized Paths

Canonical Antigravity observability paths are now:

- `observability/logs/antigravity/antigravity.log`
- `observability/logs/antigravity/antigravity_monitor.out.log`
- `observability/logs/antigravity/antigravity_monitor.err.log`
- `observability/logs/antigravity/option_bug_hunter.out.log`
- `observability/logs/antigravity/option_bug_hunter.err.log`

Legacy app-local `repos/option/logs/` is transitional only. Runtime wrappers may
point that path at the canonical observability directory for compatibility, but
0luka observability is the operational source of truth.

## Migration Note

Phase A does not force a full log-path rewrite in one pass. It establishes the
0luka-owned observability target and prevents Antigravity from remaining the
host of system survival evidence.
