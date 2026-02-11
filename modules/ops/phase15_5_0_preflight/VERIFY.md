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
[preflight] API check: curl api.github.com ... OK
[preflight] Auth check: gh auth status ... OK
[preflight] OK
0
```

## Expected Output (FAIL example — no network)
```
[preflight] DNS check: ping github.com ... FAIL
[preflight] ERROR: DNS resolution for github.com failed
[preflight] API check: curl api.github.com ... FAIL
[preflight] ERROR: api.github.com unreachable or returned error
[preflight] Auth check: gh auth status ... FAIL
[preflight] ERROR: gh auth status failed — token expired or not logged in
[preflight] BLOCKED — fix the above before running GitHub operations
1
```

## Integration
All lanes that call `gh pr`, `gh merge`, or `gh api` must run this preflight first.
