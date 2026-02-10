# Phase Cole-Run Spec

## Objective
Register `cole_run` as an official read-only tool in 0luka.

## Command Contract
- `list`: emit deterministic lexicographically sorted run ids from `cole/runs/**`.
- `latest`: emit explicit rule `max(sorted_lexicographic)`.
- `show <run_id>`: read one allowed artifact from `cole/runs/**` or `observability/**`.

## Safety
- Read-only only. No writes.
- No network access.
- No access to `interface/inbox/**`.
- Redact local user paths/tokens from output.

## Output Contract
Single-line JSON for each invocation with:
- `ok` (bool)
- `command` (string)
- command-specific fields (`runs`, `run_id`, `path`, `content`)
- deterministic ordering for list/latest
