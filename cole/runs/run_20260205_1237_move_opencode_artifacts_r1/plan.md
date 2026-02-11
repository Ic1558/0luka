# Plan: Authoritative Move of Existing Artifacts into cole/

## Intent

Move previously created artifacts into `cole/` so Cole owns the canonical copies.

## Steps

1) Move directories into `cole/outbox/`.
2) Leave tiny redirect stubs at old locations (README only) to avoid confusion.
3) Update manifest + index.

## DoD

- `cole/outbox/opencode/` contains the former `opencode/` contents
- `cole/outbox/g_reports_opencode/` contains the former `g/reports/opencode/` contents
- `cole/outbox/g_manuals_opencode/` contains the former `g/manuals/opencode/` contents
- Old locations contain only redirect README.md files
