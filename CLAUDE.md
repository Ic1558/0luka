# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Health check
python3 core/health.py              # quick
python3 core/health.py --full       # runs all 20 test suites
python3 core/health.py --json       # machine-readable

# Smoke test (full pipeline proof on real filesystem)
python3 core/smoke.py
python3 core/smoke.py --clean       # clean artifacts after

# Unified CLI
python3 -m core status              # health + queues + recent dispatches
python3 -m core dispatch             # process all inbox tasks
python3 -m core dispatch --watch     # continuous (5s interval)
python3 -m core dispatch --file <path>
python3 -m core dispatch --dry-run
python3 -m core submit --file task.yaml
python3 -m core ledger --tail 20 --status committed
python3 -m core retention --apply    # rotate old artifacts

# Tests (two locations)
python3 -m pytest core/verify/       # unit/integration (20 suites)
python3 -m pytest tests/             # e2e, stress, MCP
python3 core/verify/test_task_dispatcher.py  # single suite

# Activity feed linter
python3 tools/ops/activity_feed_linter.py --json
```

## Architecture

### Pipeline

```
submit_task() → interface/inbox/task_<id>.yaml
    → task_dispatcher.dispatch_one()
        → phase1a_resolver.gate_inbound_envelope()   # schema + hardpath gate
        → Router.execute()                            # policy + CLEC executor
        → Router.audit()                              # fs.purity, hash.match, proc.clean gates
            → phase1d_result_gate.gate_outbound_result()
            → outbox_writer → interface/outbox/tasks/<id>.result.json
        → dispatch_latest.json                        # atomic pointer
```

### Key modules

| Module | Role |
|---|---|
| `core/config.py` | ROOT resolution + all canonical paths |
| `core/task_dispatcher.py` | Inbox watcher, dispatch loop, activity feed emission |
| `core/router.py` | propose/execute/audit with policy enforcement |
| `core/clec_executor.py` | Executes CLEC ops: write_text, mkdir, copy, patch_apply, run |
| `core/phase1a_resolver.py` | Inbound gate: Draft 2020-12 jsonschema validation, ref resolution, hardpath guard |
| `core/phase1d_result_gate.py` | Outbound gate: result sanitization, evidence minimum |
| `core/submit.py` | Task submission API (envelope wrap + seal + inbox write) |
| `core/schema_registry.py` | Hand-rolled validator against `core/contracts/v1/0luka_schemas.json` |
| `core/circuit_breaker.py` | Wraps router.execute (trips after 3 failures, 60s recovery) |
| `core/run_provenance.py` | Records input/output hash per execution |
| `core/seal.py` | HMAC envelope signing |
| `core/policy.yaml` | Actor capabilities, allowed roots, required gates for commit |

### Schemas

6 locked schemas in `core/contracts/v1/0luka_schemas.json`: envelope, task, run_result, evidence_min, router_audit, dispatch_latest.

Interface schemas in `interface/schemas/`: clec_v1.yaml, router_audit_v1.json, run_provenance_v1.json, etc.

### Observability

```
observability/logs/dispatcher.jsonl        # dispatch event log
observability/logs/activity_feed.jsonl     # lifecycle events (started/completed/verified)
observability/artifacts/dispatch_latest.json  # atomic pointer to last result
observability/artifacts/router_audit/<id>.json
observability/run_provenance.jsonl
```

### Task format (clec.v1)

```yaml
task_id: example_001
author: codex
schema_version: clec.v1
ts_utc: '2026-02-19T00:00:00Z'
call_sign: '[Codex]'
root: '${ROOT}'          # NEVER hardcode /Users/ paths
intent: example.task
ops:
  - op_id: op1
    type: write_text     # write_text | mkdir | copy | patch_apply | run
    target_path: artifacts/output.txt
    content: "hello"
verify: []
```

## Invariants

- **No hardcoded paths.** All paths relative to ROOT. The no-hardpath guard rejects `/Users/` in any payload.
- **Atomic writes only.** Write `.tmp` then `os.replace()`.
- **Provenance required.** Every execution produces a RunProvenance row.
- **Schema fail = reject.** Never warn-and-continue on schema failure.
- **Dependencies:** pyyaml, jsonschema. Python stdlib otherwise.

## Directory layout

- `core/` — kernel pipeline logic and tests (`core/verify/test_*.py`)
- `core_brain/` — governance, agent catalog, compiler
- `interface/` — inbox, outbox, completed, rejected, schemas
- `observability/` — logs, artifacts, incidents, provenance
- `tools/` — operational scripts (save_now.zsh, activity_feed_linter.py)
- `g/` — knowledge (MLS), reports, manuals, sessions
- `tests/` — integration and e2e tests
