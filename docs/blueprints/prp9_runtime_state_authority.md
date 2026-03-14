# PRP-9: Runtime State Authority Hardening

## Scope

This step hardens runtime state path authority without redesigning runtime behavior.

Implemented files:
- `core/runtime/__init__.py`
- `core/runtime/runtime_state_resolver.py`
- `runtime/runtime_service.py`
- `interface/operator/mission_control_server.py`
- `core/verify/test_runtime_state_resolver.py`

## RuntimeStateResolver Purpose

`RuntimeStateResolver` is the canonical runtime state path authority.

It resolves and exposes runtime state paths from `runtime_root`:
- `state_dir()`
- `qs_runs_dir()`
- `current_system_file()`
- `alerts_file()`
- `approval_actions_file()`
- `approval_log_file()`
- `remediation_history_file()`
- `system_model_file()`

No direct string path construction is required for migrated modules.

## Canonical Path Authority

`resolve_runtime_root(...)` is fail-closed:
- requires runtime root input or env (`LUKA_RUNTIME_ROOT` or `RUNTIME_ROOT`)
- requires resolved root to exist

This removes implicit root assumptions and enforces deterministic runtime path resolution.

## Migrated References (mission_control_server.py)

Migrated runtime state access:
- `state/alerts.jsonl` -> resolver `alerts_file()`
- `state/approval_actions.jsonl` -> resolver `approval_actions_file()`
- `state/approval_log.jsonl` -> resolver `approval_log_file()`
- `state/remediation_history.jsonl` -> resolver `remediation_history_file()`
- `state/qs_runs` -> resolver `qs_runs_dir()`
- `state/system_model.json` -> resolver `system_model_file()`

Removed hardcoded runtime root fallback (`/Users/icmini/0luka_runtime`) from this module.

## RuntimeService Exposure

`runtime/runtime_service.py` now exposes:
- `get_runtime_state_resolver()`

This allows runtime service consumers to use state paths through the authority layer.

## Behavior Boundary

This is a path-authority hardening refactor only.
- No bridge redesign
- No runtime behavior redesign
- No PM2/launchd/broker changes

## Validation

Targeted validation executed:

```bash
python3 -m py_compile core/runtime/__init__.py core/runtime/runtime_state_resolver.py runtime/runtime_service.py interface/operator/mission_control_server.py core/verify/test_runtime_state_resolver.py core/verify/test_runtime_service.py
pytest -q core/verify/test_runtime_state_resolver.py core/verify/test_runtime_service.py
```

Result:
- targeted tests passed

Full `pytest -q` collection failures are workspace-wide and out of scope for this PRP-9 step.
