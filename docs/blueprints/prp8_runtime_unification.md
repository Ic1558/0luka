# Blueprint: PRP-8 — Runtime Service Unification (Scaffold Integration)

## Scope
This step introduces the runtime boundary scaffold and integrates it into:
- Bridge consumer
- Dispatcher

This is not a bridge redesign.

## Implemented Components

### 1. RuntimeService core
File:
- `runtime/runtime_service.py`

Purpose:
- resolve `runtime_root` dynamically (`runtime_root` arg -> `RUNTIME_ROOT` -> `ROOT`)
- validate TaskSpec v2 at runtime boundary
- normalize bridge v1-compatible tasks into TaskSpec v2-compatible shape
- append runtime transitions to system ledger:
  - `observability/stl/ledger/global_beacon.jsonl`

### 2. Bridge boundary integration
File:
- `tools/bridge/bridge_consumer.py`

Role:
- run RuntimeService boundary validation before existing consumer validation
- preserve bridge v1 compatibility via normalization
- ledger-bind key transitions:
  - boundary rejection
  - dispatch success

### 3. Dispatcher integration
File:
- `core/task_dispatcher.py`

Role:
- bind dispatch start/end transitions to RuntimeService ledger events
- preserve existing dispatch behavior and compatibility

## Validation
File:
- `core/verify/test_runtime_service.py`

Covers:
- runtime root resolution
- bridge v1 compatibility normalization
- lane mismatch rejection
- ledger transition append

## Non-Goals
- no PM2/launchd changes
- no broker integration
- no bridge transport redesign
- no change to ag_bridge or bridge_task_processor logic
