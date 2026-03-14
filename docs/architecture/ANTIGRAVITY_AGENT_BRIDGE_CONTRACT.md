# Antigravity Agent Bridge Contract (AG-1)

## 1. Governance Principles (Non-Negotiable)
P1. Antigravity must not call 0luka agents directly. All requests route through the bridge adapter.

P2. Bridge is a governed adapter. It must validate schema, enforce allowlist, emit audit, and block unsafe tasks. It must not bypass dispatcher, self-route, or execute side effects.

P3. 0luka dispatcher is the source of execution truth. Antigravity is the cockpit, not the runtime owner.

P4. Bridge respects active policy. If `core/policy.yaml` has `freeze_state: true`, bridge must block all requests.

## 2. Request Schema (v1)

```yaml
# AG Bridge Request v1
id: <uuid>
source: "antigravity"
agent: <string>
task: <string>
args: <object>
created_at_utc: <iso8601z>
```

## 3. Response Schema (v1)

```yaml
# AG Bridge Response v1
id: <uuid>
status: ok | error | blocked
result: <object | null>
error: <string | null>
policy_blocked: <bool>
```

## 4. Task Envelope Mapping to 0luka Task
The AG-2 adapter translates bridge requests into `task_spec_v2.yaml`-conformant tasks and submits them through `submit_task()`.

Mapping:
- `bridge.id` -> `task_id`
- `bridge.source` -> `author` (normalized to allowed task author)
- `bridge.agent` -> `lane` (for example `cole`, `lisa`)
- `bridge.task` -> `intent` (for example `cole.search_docs`)
- `bridge.args` -> `operations[0].params`
- `bridge.created_at_utc` -> `created_at_utc`

Known prerequisite for AG-2:
- `task_spec_v2.yaml` currently limits `author` to `[liam, gmx, boss]`
- bridge-originated requests need `"antigravity"` added to author enum
- this enum change is deferred to AG-2 and is not part of AG-1

## 5. Allowlist (v1 Scope)
Allowed:
- `cole.search_docs` -> lane `cole`
- `lisa.exec_shell` -> lane `lisa`

Deferred:
- `paula.run_strategy` (requires governance approval before live use)
- `gmx.*` (requires stricter governance layer)

## 6. Explicitly Blocked Categories
Blocked regardless of allowlist:
- any command containing `rm -rf`, `sudo`, or system paths outside allowed roots
- any direct filesystem access outside `~/0luka` allowed roots
- any network call that bypasses 0luka policy
- any request with `source != "antigravity"`
- any request with `agent/task` not in v1 allowlist

## 7. Audit Fields (Required)
Every bridge request reaching the adapter must emit an audit entry:

```json
{
  "ts_utc": "<iso8601z>",
  "category": "bridge_request",
  "source": "antigravity",
  "agent": "<agent>",
  "task": "<task>",
  "request_id": "<uuid>",
  "status": "accepted | rejected | blocked",
  "reason": "<string>"
}
```

Target sink:
- `observability/logs/activity_feed.jsonl` through the existing append helper path

## 8. Unsafe Command Detection (Specification Only, AG-6 Implementation)
Detection surface:
- `rm -rf` literal or equivalent in any arg string
- `sudo` prefix in any arg string
- path prefixes: `/etc/`, `/System/`, `/usr/`, `~/.ssh/`, `~/.gnupg/`
- shell metacharacters for injection: `&&`, `||`, `;`, `|`, backticks, `$()`

Bridge behavior on detection:
- reject request
- audit with `status: rejected`

## 9. Relationship to 0luka Pipeline
```text
Antigravity Agent
    | bridge request (AG schema v1)
    v
tools/ag_bridge.py              <- AG-2
    | translate -> task_spec_v2
    | submit_task()
    v
interface/inbox/
    |
    v
core/task_dispatcher.py
    |
    v
Lisa / Cole agents
    |
    v
interface/outbox/result
```

## 10. Known Prerequisites for AG-2
- add `"antigravity"` to `author` enum in `interface/schemas/task_spec_v2.yaml`
- create `tools/bridge/` as Python package
- `kernel_boundaries.py` already registers `tools.bridge.*` for execution bridge boundary ownership

