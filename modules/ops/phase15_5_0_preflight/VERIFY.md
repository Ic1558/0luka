# Phase 15.5.0 — GitHub Preflight Network Gate

## Purpose
Block GitHub operations (PR create/merge/view) when network or auth is down.
Prevents misdiagnosing API failures as system bugs.

## Run
```bash
./tools/ops/preflight_github.zsh
echo $?
```

## Expected Output (PASS)
```
[preflight] DNS check: ping github.com ... OK
[preflight] API check: curl https://api.github.com ... OK
[preflight] Auth check: gh auth status ... OK
[preflight] OK
0
```

## Expected Output (FAIL example — stop on first failure)
```
[preflight] DNS check: ping github.com ... FAIL
[preflight] ERROR: DNS resolution for github.com failed
1
```

## API outage fallback rule (API-free)
If `gh` fails with `error connecting to api.github.com` or `Could not resolve host`,
run only Git-safe checks below and stop before merge:

```bash
git ls-remote --heads origin
git fetch --prune origin
git show-ref --heads --tags
```

Do **not** merge, close, or mutate PR state while preflight is failing.

## Integration
All lanes that call `gh pr`, `gh merge`, or `gh api` must run this preflight first.
