# Interpreted Observability Milestone

## Classification

0luka is currently an **Interpreted Observability System**.

It is **not yet**:

- a decision system
- an automated remediation system
- an artifact repair system

## System Chain

```text
runtime execution
  -> qs run manifest
    -> qs status payload
      -> Mission Control qs_run projection
        -> interpretation enrichment
          -> Mission Control API
            -> Mission Control UI
```

## Components Involved

- `repos/qs/src/universal_qs_engine/run_manifest.py`
  - defines canonical QS run state and artifact attachment model
- `repos/qs/src/universal_qs_engine/status_surface.py`
  - projects a `RunManifest` into a payload
- `tools/ops/run_interpreter.py`
  - derives bounded interpretation signals from run + artifact state
- `interface/operator/mission_control_server.py`
  - enriches qs run payloads with interpretation fields and serves read-only APIs
- `interface/operator/templates/mission_control.html`
  - renders proof/run/artifact visibility and interpretation signals
- `interface/operator/tests/test_mission_control_ui_slice_5.py`
  - verifies the UI signal rendering hooks

## Current Signals Supported

Run interpretation currently supports:

- `COMPLETE`
- `PARTIAL`
- `MISSING_PROOF`
- `INCONSISTENT`

Mission Control currently renders and consumes:

- `signal`
- `artifact_count`
- `expected_artifacts`
- `missing_artifacts`

Fallback text present in the UI:

- `Signal unavailable`

## API and UI Surfaces Present

Mainline now includes:

- `/api/proof_artifacts`
- `/api/proof_artifacts/{artifact_id}`
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`
- `/api/qs_runs/{run_id}/artifacts`

Mission Control UI now provides an operator-facing proof consumption path:

```text
qs run
  -> linked artifacts
    -> artifact detail
```

## Signal Origin Confirmation

The signal rendered in the UI originates from the Mission Control qs run projection:

1. `load_qs_runs()` and `load_qs_run()` in `interface/operator/mission_control_server.py`
   attach proof artifacts to the base run payload.
2. `_attach_qs_run_interpretation(...)` calls `interpret_run(...)`.
3. The resulting fields are written into the read-model payload:
   - `artifact_count`
   - `expected_artifacts`
   - `missing_artifacts`
   - `signal`
4. `mission_control.html` renders `entry.signal` in the QS run list.

This confirms that the UI signal comes from the QS run projection, not from ad-hoc UI logic.

## Evidence of Verification

Targeted tests passed:

- `python3 -m pytest -q core/verify/test_mission_control_server.py interface/operator/tests/test_mission_control_ui_slice_5.py`
- Result: `21 passed`

Repository-wide check:

- `python3 -m pytest -q`
- started in this verification pass, but did not produce a completion result within the observation window
- therefore this milestone note records the targeted milestone evidence as confirmed green, while the full-suite result remains unconfirmed in this pass

## What the System Can Now Observe

The system can now:

- expose QS run state
- expose linked proof artifacts
- expose artifact detail
- derive bounded interpretation signals from run + artifact state
- render those signals in Mission Control for operator inspection

## What the System Still Cannot Do

The system still does **not**:

- persist interpretation decisions
- expose `/api/decisions`
- trigger remediation or action selection
- repair or rewrite artifact/history data
- mutate runtime state from interpretation outputs

## Milestone Meaning

This milestone establishes an interpreted read model on top of the existing observability surfaces.

It is the point where 0luka moves from:

- proof/run visibility only

to:

- proof/run visibility with bounded run-state interpretation

without crossing into control-plane autonomy.
