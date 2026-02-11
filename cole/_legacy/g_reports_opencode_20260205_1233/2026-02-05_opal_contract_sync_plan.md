# Plan Report: OPAL Contract Drift + MBP Setup Menu

Date: 2026-02-05

## Goals

1) Close Contract\u2194Implementation drift for `GET /api/jobs`.
2) Make `Ic1558/core` authoritative (SOT) and ensure `0luka` consumes it via env/config discovery (no hard paths).
3) Provide validation + rollback paths to prevent mistakes.
4) Provide an MBP control-plane script (`setup`) that uses env-based discovery.

## Constraints / Non-Goals

- Do not invent facts; verify by reading code and/or hitting localhost.
- Least disruptive consumption change preferred (avoid submodule conversion unless necessary).
- No hardcoded IP/path in control-plane scripts; use env vars.

## Plan (Ordered)

### A) Verify runtime behavior

- Confirm `GET /api/jobs` response top-level shape (dict/map vs list) by:
  - `curl http://127.0.0.1:7001/api/jobs` (if running)
  - fallback to implementation code (`opal_api_server.py`, `JobsDB.get_all_jobs`).

### B) Patch SOT (Ic1558/core)

- Clone `git@github.com:Ic1558/core.git` to `/Users/icmini/repos/core` (if missing).
- Add `contracts/v1/opal_api.openapi.json` with `GET /api/jobs` schema matching runtime.
- Bump `VERSION` MINOR.
- Add/update `CHANGELOG.md`.
- Commit + push.

### C) Make 0luka consume SOT contract

Choose Option 1 (least disruptive): `CORE_CONTRACTS_URL` discovery.

- Update OPAL server `GET /openapi.json` to fetch and return contract bytes from:
  - `CORE_CONTRACTS_URL` (URL base, URL file, local path, or file://)
  - default to `https://raw.githubusercontent.com/Ic1558/core/main`
- Remove hardcoded absolute default root in runtime config.

### D) Add minimal validation command

- Add `tools/validate_opal_contract_runtime.py` to verify:
  - Served OpenAPI contains `GET /api/jobs`
  - Runtime `GET /api/jobs` returns dict + required fields (`id`, `status`)

### E) Add rollback script

- Add `tools/rollback_git_commit.zsh` which performs `git revert` safely (no history rewrite).

### F) MBP setup menu template

- Provide `opencode/templates/setup` (and a manual) using env vars:
  - `OPAL_API_BASE`, `SSH_HOST_ALIAS`, `OPAL_REMOTE_ROOT`, `OPAL_LOCAL_ARTIFACTS_DIR`

## Definition Of Done (DoD)

- `curl -fsS "$OPAL_API_BASE/openapi.json"` contains `GET /api/jobs`.
- `curl -fsS "$OPAL_API_BASE/api/jobs"` returns successfully.
- `python3 tools/validate_opal_contract_runtime.py` passes.
- Setup menu script is ready to copy to MBP and run.

## Risk Control

- All changes are reversible via `git revert` (see rollback manual).
- OPAL server serves contract bytes directly (enables byte-identical SOT serving).
