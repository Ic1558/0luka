# Report: Migrate Existing OpenCode Artifacts Into cole/

## What happened

This run retroactively formalized previously created artifacts into Tracked Mode by taking a non-destructive snapshot into `cole/_legacy/`.

## Source paths (pre-existing)

- `opencode/`
- `g/reports/opencode/`
- `g/manuals/opencode/`

## Destination snapshot (created)

- `cole/_legacy/opencode_20260205_1233/`
- `cole/_legacy/g_reports_opencode_20260205_1233/`
- `cole/_legacy/g_manuals_opencode_20260205_1233/`

## Notes

- This is a copy (mirror), not a move. Originals remain intact.
- If Boss later wants authoritative move, we can do a second tracked run that deletes/relocates originals after verification.
