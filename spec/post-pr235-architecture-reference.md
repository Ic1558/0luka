# Post-PR235 Architecture Reference

This note records the canonical architecture truth for the system boundary after PR #235.

## Recorded architecture truth

- Kernel active
- Observability active
- Mission Control read surfaces on `main`
- Phase C.0 present as a no-write dry-run classifier
- Phase D absent and intentionally parked
- `repos/qs` frozen canonical

## Classification

This note records the current system as:

- `stable observable platform with bounded decision awareness`

## Scope

- docs-only
- no implementation changes
- no test changes
- no changes inside `repos/qs`

## Non-Claims

- does not unpark Phase D
- does not add persistence
- does not add endpoints
- does not promote historical branches
