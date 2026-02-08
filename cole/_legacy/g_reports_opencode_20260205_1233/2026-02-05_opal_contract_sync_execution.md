# Execution Report: OPAL Contract Drift + MBP Setup Menu

Date: 2026-02-05

## What Was Verified

### Runtime shape for `GET /api/jobs`

- Live check (when OPAL is running): `GET /api/jobs` returns a JSON object/map (dict) keyed by job id.
- Code evidence:
  - `runtime/apps/opal_api/opal_api_server.py` declares `response_model=dict[str, JobDetail]` for `GET /api/jobs`.
  - `runtime/apps/opal_api/common.py` `JobsDB.get_all_jobs()` returns the jobs DB dict.

Conclusion: contract must define `GET /api/jobs` response as `type: object` with `additionalProperties: JobDetail`.

## Changes Made

### A) Core SOT repo (`Ic1558/core`)

- Cloned to: `/Users/icmini/repos/core`
- Added contract file: `contracts/v1/opal_api.openapi.json`
  - Includes `GET /api/jobs` + existing `POST /api/jobs` + `GET /api/jobs/{id}`.
- Bumped version: `VERSION` `1.0.0` -> `1.1.0`
- Added: `CHANGELOG.md`

Commit:
- Core commit: `ac3118f126f202a8d0c607dd7be7bb16905bbe6a` (pushed to `origin/main`)

### B) Executor repo (`/Users/icmini/0luka`)

- Updated OPAL server to serve OpenAPI from SOT via env/config discovery:
  - `runtime/apps/opal_api/opal_api_server.py` now loads bytes from `CORE_CONTRACTS_URL` (or `CORE_CONTRACT_URL`) and returns them from `GET /openapi.json`.
  - Default: `https://raw.githubusercontent.com/Ic1558/core/main` (as URL base).
- Removed hardcoded absolute project root default:
  - `runtime/apps/opal_api/common.py` now derives a safe default root from file location and supports `LUKA_BASE`/`OLUKA_ROOT` env.
- Added validator:
  - `tools/validate_opal_contract_runtime.py`
- Added rollback helper:
  - `tools/rollback_git_commit.zsh`

Commits:
- `2b2c1b42eb6029e737c524e3be17b176f2f8f223` (SOT load + validator + rollback)
- `288bf996d4f2bb83a038bc60011fb6a1ff5f9851` (cleanup: simplify env resolution)

## Environment / Dependency Fix

- Installed into OPAL venv: `python-multipart` (required for FastAPI `Form`/`File` route wiring).
  - Verified: `runtime/venv/opal/bin/pip show python-multipart`.

## Verification Commands (DoD)

Assuming OPAL is reachable at `OPAL_API_BASE`:

```bash
export OPAL_API_BASE="http://127.0.0.1:7001"

# 1) openapi contains GET /api/jobs
curl -fsS "$OPAL_API_BASE/openapi.json" | python3 -c 'import sys,json; s=json.load(sys.stdin); print("get" in s["paths"]["/api/jobs"])'

# 2) runtime endpoint works
curl -fsS "$OPAL_API_BASE/api/jobs" >/dev/null

# 3) validator passes
OPAL_API_BASE="$OPAL_API_BASE" python3 tools/validate_opal_contract_runtime.py
```

Expected:
- prints `True`
- `/api/jobs` returns HTTP 200
- validator prints `OK: contract and runtime agree for GET /api/jobs`

## Rollback

Use `git revert` via the helper script (no history rewrite):

```bash
# Revert latest commit in 0luka
tools/rollback_git_commit.zsh /Users/icmini/0luka HEAD

# Revert the core contract commit
tools/rollback_git_commit.zsh /Users/icmini/repos/core ac3118f126f202a8d0c607dd7be7bb16905bbe6a
```
