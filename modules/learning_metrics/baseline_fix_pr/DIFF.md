# DIFF — Baseline Health Tracked

## Added (tracked baseline artifacts)
- `interface/schemas/clec_v1.yaml`
- `interface/schemas/0luka_result_envelope_v1.json`
- `interface/schemas/0luka_schemas_v1.json`
- `interface/schemas/phase1a_routing_v1.yaml`
- `interface/schemas/phase1a_task_v1.json`
- `interface/schemas/router_audit_v1.json`
- `interface/schemas/run_provenance_v1.json`

## Updated
- `core/smoke.py`
  - module-bound submit/dispatch calls
  - sync `core.clec_executor.ROOT` to current `ROOT`
  - `written_file` step reports ROOT-anchored path detail
- `core/verify/test_phase1d_result_gate.py`
  - `test_back_resolve_trusted_uri` now sets/restores `0LUKA_ROOT` explicitly

## Behavior
- Clean clone/worktree now has required schema files tracked.
- `pytest core/verify -q` no longer depends on local untracked schema artifacts.
