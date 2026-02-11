# Plan: Migrate Existing OpenCode Artifacts Into cole/

## Intent

Bring previously created artifacts (reports/manuals/templates) under `cole/` without breaking anything.

## Mode

Tracked Mode (retroactive formalization).

## Strategy

- Non-destructive migration: copy/snapshot current artifacts into `cole/_legacy/`.
- Record source paths and what was copied.
- Update `cole/manifests/tk_<tk_id>.index.yaml`.

## DoD

- `cole/runs/<run_id>/manifest.yaml` exists
- Snapshot copies exist under `cole/_legacy/*_20260205_1233/`
- Index exists under `cole/manifests/`
- No original artifacts deleted
