# Antigravity Runtime State Ownership

This directory is the bounded 0luka-owned runtime state namespace for current
Antigravity service state.

Canonical current-state examples:

- `runtime/state/antigravity/bootstrap_state.json`
- `runtime/state/antigravity/antigravity_scan_runtime.json`
- `runtime/state/antigravity/antigravity_realtime_runtime.json`

Rules:

- runtime state is mutable current service state only
- historical inspection logs stay under `observability/logs/antigravity/`
- repo-local state/cache files are transitional only and must not be treated as
  operational truth
