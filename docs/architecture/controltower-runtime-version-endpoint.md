# Design Spec: GET /api/runtime/version

Status: DESIGN ONLY — not implemented
Scope: control_tower.py (Antigravity HQ)
Activation: post-freeze / post-verification phase
Authored: CLC
Revised: stress-test corrections applied

---

## Problem

After a patch is written to disk, there is no way to confirm whether the running
process has loaded the new code or is still executing from the old memory image.

This creates ambiguity in three situations:
- after a PM2 restart (did the new code actually load?)
- during launchd migration cutover (which supervisor / which python?)
- during incident diagnosis (is the live behaviour matching the current source?)

---

## Solution

A read-only endpoint that exposes the runtime identity captured at process start.

```
GET /api/runtime/version
```

The values are captured once at startup and served from an in-memory struct.
No disk reads, no git queries, no external calls per request.

This endpoint is process-scoped, not host-scoped. It reports the identity of
the process serving the request only. Multiple instances may exist simultaneously.

---

## Response Schema

```json
{
  "service": "control_tower",
  "pid": 97282,
  "git_commit": "abc1234",
  "git_branch": "main",
  "git_dirty": false,
  "started_at": "2026-03-13T03:47:21.123456+00:00",
  "code_path": "/Users/icmini/0luka/repos/option/modules/antigravity/realtime/control_tower.py",
  "python_executable": "/Users/icmini/0luka/repos/option/venv/bin/python3",
  "supervisor_hint": "pm2",
  "build_fingerprint": "abc1234:/Users/icmini/0luka/repos/option/modules/antigravity/realtime/control_tower.py"
}
```

When working tree is dirty:
```json
{
  "git_commit": "abc1234",
  "git_dirty": true,
  "build_fingerprint": "abc1234-dirty:/Users/icmini/0luka/repos/option/modules/antigravity/realtime/control_tower.py"
}
```

---

## Fields

| Field | Source | Captured when |
|---|---|---|
| `service` | hardcoded `"control_tower"` | startup |
| `pid` | `os.getpid()` | startup |
| `git_commit` | `git rev-parse --short HEAD` in repo CWD | startup |
| `git_branch` | `git rev-parse --abbrev-ref HEAD` | startup |
| `git_dirty` | `git diff --quiet HEAD` exit code (0=clean, 1=dirty) | startup |
| `started_at` | `datetime.now(timezone.utc).isoformat()` | startup |
| `code_path` | `os.path.realpath(__file__)` | startup |
| `python_executable` | `sys.executable` | startup |
| `supervisor_hint` | parent process chain inference (best-effort) | startup |
| `build_fingerprint` | `{git_commit}[-dirty]:{code_path}` | startup |

---

## In-Memory Struct

One dict, populated at module load, wrapped in MappingProxyType to enforce
the never-mutate-after-startup rule at the language level:

```python
import types

_RUNTIME_VERSION_INFO = {
    "service": "control_tower",
    "pid": ...,
    "git_commit": ...,
    "git_branch": ...,
    "git_dirty": ...,
    "started_at": ...,
    "code_path": ...,
    "python_executable": ...,
    "supervisor_hint": ...,
    "build_fingerprint": ...,
}

RUNTIME_VERSION_INFO = types.MappingProxyType(_RUNTIME_VERSION_INFO)
```

The endpoint reads RUNTIME_VERSION_INFO. Nothing else.

---

## git_dirty Detection

```
git diff --quiet HEAD
exit code 0 → git_dirty = False
exit code 1 → git_dirty = True
non-zero other / git unavailable → git_dirty = null
```

When `git_dirty` is True, `build_fingerprint` must reflect this:

```
{git_commit}-dirty:{code_path}
```

This is the correct way to distinguish:
- a process that started from a committed state
- a process that started from a working tree with uncommitted patches

Note: `git_commit` alone cannot detect uncommitted changes. Without `git_dirty`,
the endpoint cannot answer the question "did the patch actually load?"

---

## Supervisor Hint — Inference Logic

Walk the parent process chain using case-insensitive substring matching.
Never use exact name comparisons.

```
p = current process
parent = p.parent()
grandparent = parent.parent()

if "launchd" in parent.name().lower():
    supervisor_hint = "launchd"

elif "pm2" in parent.name().lower():
    supervisor_hint = "pm2"

elif "dotenvx" in parent.name().lower():
    if "pm2" in grandparent.name().lower():
        supervisor_hint = "pm2"
    elif "launchd" in grandparent.name().lower():
        supervisor_hint = "launchd"
    else:
        supervisor_hint = "unknown"

else:
    supervisor_hint = "unknown"
```

This handles the verified real-world process chain:

```
python3 (control_tower.py) ← dotenvx ← PM2 v6.0.14: God Daemon ← PID 1
```

psutil dependency: optional. If unavailable → `supervisor_hint = "unknown"`.
Startup must never fail because psutil is absent.

---

## Process-Scoped Limitation

This endpoint reports the identity of the specific process responding to port 8089.

If multiple instances of control_tower.py are running simultaneously:
- each instance reports its own pid, supervisor_hint, and started_at
- only the instance that owns port 8089 is reachable via this endpoint
- the other instance is invisible to this endpoint

To enumerate all instances, use external tools:
```
lsof -nP -iTCP:8089 -sTCP:LISTEN
ps aux | grep control_tower
pm2 list
launchctl list | grep antigravity
```

---

## What This Endpoint Must NOT Do

- Must not call `git` on each request
- Must not read from disk on each request
- Must not mutate any runtime state
- Must not contact PM2, launchd, or any external service
- Must not block startup if git is unavailable (use `"unknown"` as fallback)
- Must not assume it is the only running instance

---

## Error Handling at Startup

All capture operations must be wrapped individually. A failure in any single
field must not prevent startup or corrupt other fields.

| Field type | Default on failure |
|---|---|
| string fields | `"unknown"` |
| bool fields (`git_dirty`) | `null` |
| int fields (`pid`) | `null` |

---

## version_source (removed)

The field `version_source: "runtime"` was removed. It was a constant with no
operational meaning in this context. If future variants are added (e.g., a
build-time baked version distinct from runtime inspection), reintroduce with
documented values: `runtime`, `build`, `package`.

---

## Use Cases This Enables

| Question | Answer source |
|---|---|
| Did PM2 restart load the new code? | `git_commit` + `git_dirty` combined |
| Was the process started from a patched but uncommitted tree? | `git_dirty: true` |
| Is launchd using venv python or system python? | `python_executable` |
| When did this process start? | `started_at` |
| Which supervisor launched this process? | `supervisor_hint` |
| Which specific process instance is responding? | `pid` |
| Does disk code match runtime? | compare disk `git rev-parse` + `git diff` vs endpoint |

---

## Activation Condition

This feature must not be implemented during frozen state.

Recommended activation window: after Verification Phase completes, as a
standalone enhancement before or alongside launchd cutover.

It is safe to implement independently of the supervisor migration — it adds an
endpoint and does not change any existing behaviour.

---

## File Impact (when implemented)

Single file: `modules/antigravity/realtime/control_tower.py`

Two additions:
1. `RUNTIME_VERSION_INFO` MappingProxy populated at module load
2. `GET /api/runtime/version` FastAPI route (read-only, returns the proxy)

No other files affected.
No new required dependencies. psutil treated as optional.
