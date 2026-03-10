# 0luka Step 1 Completion — Proof Consumption Surface

## Current mainline truth

Main now includes these proof-consumption surfaces:

- `/api/proof_artifacts`
- `/api/proof_artifacts/{artifact_id}`
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`
- `/api/qs_runs/{run_id}/artifacts`
- Mission Control proof-consumption page wiring

## Operational meaning of Step 1

Operator can now inspect:

- run list
- run-linked artifacts
- artifact detail

through bounded read-only surfaces on main.

`Step 1 complete enough`

## What remains intentionally absent

Step 1 does not include:

- decision persistence
- `/api/decisions`
- remediation/action selection
- approval/remediation UI expansion
- planner/executor split
- Phase D autonomy
- any mutation of runtime data
- any changes to `repos/qs`

## Boundary lock for Step 2

Step 2 may touch:

- minimal control-plane reconstruction
- bounded verification/decision surfaces
- fresh branches only
- bounded PRs only

Step 2 must not touch:

- historical heavy branch revival
- `repos/qs`
- broad UI redesign
- uncontrolled autonomy
- mixed-lane feature bundles

## Final classification

`Step 1 complete enough; Step 2 not yet opened`

## Short architectural summary

0luka is currently:

`stable observable platform with bounded decision awareness`
