# Phase 9 Linguist Mapping Spec v0

## Purpose
Define deterministic NLP-to-intent mapping for Phase 9 using the fixture source of truth at `modules/nlp_control_plane/tests/phase9_vectors_v0.yaml`.
The mapping outputs a valid `clec.v1` task payload (or fail-closed result) without runtime execution.

## Non-goals
- No dispatcher/submit/runtime integration.
- No task execution.
- No launchd wiring.
- No mutation of activity feed from this spec alone.

## Input Contract
Linguist input is a normalized request object:
- `input_text`: non-empty natural language request.
- `context.root`: logical `${ROOT}`.
- `context.mode`: optional mode hint (`ops|build|audit`).

## Output Contract
Linguist output is exactly one of:
1. `mapped_task`
- `expected_intent`: one of taxonomy intents.
- `required_slots`: fully populated, policy-compliant slots.
- `expected_result`: `submit_accepted`.

2. `needs_clarification`
- `reason`: deterministic rule failure reason.
- `expected_result`: `needs_clarification`.

## Taxonomy Link
Allowed intents are exactly those declared in `modules/nlp_control_plane/tests/phase9_vectors_v0.yaml` under `taxonomy.allowed_intents`:
1. `ops.write_text`
2. `ops.append_text`
3. `ops.mkdir`
4. `ops.list_dir`
5. `ops.read_text`
6. `ops.run_command_safe`
7. `audit.lint_activity_feed`
8. `audit.run_pytest`
9. `kernel.enqueue_task`
10. `kernel.status.dispatcher`

Any intent outside this list must fail-closed with `needs_clarification`.

## Slot Schema Per Intent
| Intent | Required Slots | Extra Constraints |
|---|---|---|
| `ops.write_text` | `path`, `content` | `path` must satisfy path policy |
| `ops.append_text` | `path`, `content` | `path` must satisfy path policy |
| `ops.mkdir` | `path` | `path` must satisfy path policy |
| `ops.list_dir` | `path` | `path` must satisfy path policy |
| `ops.read_text` | `path` | `path` must satisfy path policy |
| `ops.run_command_safe` | `command`, `allowlist_id` | `allowlist_id` must equal `cmd.safe.v0` |
| `audit.lint_activity_feed` | `command_id`, `command` | `command_id` must equal `activity_feed_linter.canonical`; shell expansion forbidden |
| `audit.run_pytest` | `command` | command must equal `python3 -m pytest tests/ -q` |
| `kernel.enqueue_task` | `task.schema_version`, `task.intent`, `task.ops[]` | `task.schema_version` must equal `clec.v1`; each op typed; `write_text` requires `target_path` + `content` |
| `kernel.status.dispatcher` | `probe` | `probe` must equal `launchd.dispatcher.status` |

## Path Policy Rules
All path-like fields are ROOT-relative only:
- Paths must be non-empty.
- Paths must not be absolute.
- Paths must not contain traversal (`..`).
- Paths are interpreted relative to `${ROOT}`.

Path policy applies to:
- `required_slots.path`
- `required_slots.task.ops[].target_path`

## Command Policy Rules
- `ops.run_command_safe` requires `allowlist_id=cmd.safe.v0`.
- `audit.lint_activity_feed` requires:
  - `command_id=activity_feed_linter.canonical`
  - canonical command template with `${ROOT}` placeholders.
  - no shell expansion patterns (for example `$(`...`)` or backticks).
- `kernel.status.dispatcher` must use probe template only; no raw shell command payload.

## Fail-Closed Rules
Return `needs_clarification` when any of these occur:
- intent not in taxonomy.
- missing required slots for the resolved intent.
- policy violations (path/command/allowlist/probe constraints).
- ambiguous request that maps to multiple intents or incomplete slots.

No partial mapping is allowed.

## Traceability
Each mapping decision should be traceable to fixture vectors and policy rules:
- `source_fixture`: `modules/nlp_control_plane/tests/phase9_vectors_v0.yaml`
- `intent`
- `slot_validation_result`
- `policy_checks`
- `result`: `submit_accepted` or `needs_clarification`

For design scope, traceability is specification-level only; runtime event emission is out of scope.
