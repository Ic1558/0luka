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

## Migration Note

Phase A does not force a full log-path rewrite in one pass. It establishes the
0luka-owned observability target and prevents Antigravity from remaining the
host of system survival evidence.
