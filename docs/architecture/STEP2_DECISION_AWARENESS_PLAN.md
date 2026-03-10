# 0luka Step 2 Design Plan

## Purpose

Step 2 introduces `Decision Awareness` on top of the Step 1 proof-consumption surface.

This step is design-first. It exists to define bounded interpretation surfaces before any new implementation lane opens.

## Current Baseline

Current mainline already provides:

- proof artifact inventory
- proof artifact detail
- qs run list/detail
- per-run artifact listing
- Mission Control proof-consumption UI wiring

Current architectural classification:

- stable observable platform with bounded decision awareness

Current invariants that remain locked:

- `repos/qs` is frozen canonical
- Mission Control remains read-only
- no approval/remediation mutation is introduced by Step 2
- no historical heavy-branch revival is allowed

## Step 2 Goal

Step 2 adds bounded interpretation of proof-consumption state.

It does not add autonomy.

It does not add write paths.

It does not add remediation.

Core idea:

```text
observe -> interpret -> signal
```

## What Step 2 Should Add

### 1. Run Interpretation Model

Each QS run should become interpretable as a bounded decision object.

Candidate shape:

```text
qs_run
  -> artifacts
  -> expected_artifacts
  -> missing_artifacts
  -> status_signal
```

This is not yet persistence. It is a model boundary.

### 2. Artifact Classification

Artifacts should be classifiable by role, not only by presence.

Safe initial categories:

- `proof`
- `evidence`
- `report`
- `derived`

This classification must remain read-only and derived from existing artifact surfaces.

### 3. Proof Completeness Signals

Runs should be interpretable through bounded completeness states.

Candidate states:

- `COMPLETE`
- `PARTIAL`
- `MISSING_PROOF`
- `INCONSISTENT`

These are operator-facing interpretation signals, not action triggers.

### 4. Operator Signals

Mission Control should eventually display bounded decision-awareness signals such as:

- run health
- artifact completeness
- missing evidence

These remain informational.

No approval path.

No remediation path.

No mutation path.

## What Step 2 Must Not Add

Step 2 must not include:

- approval actions
- remediation actions
- queue writes
- planner/executor split
- historical Phase C/D resurrection
- broad UI redesign
- runtime data mutation
- any change inside `repos/qs`

## Architectural Boundary

Step 1:

```text
run -> artifacts -> artifact detail
```

Step 2:

```text
run -> artifacts -> interpretation -> operator signal
```

That means Step 2 is the first layer that asks:

- what does this evidence chain mean?

But it still does not ask:

- what action should the system take?

## Safe Execution Discipline

When Step 2 implementation starts later, it should follow these rules:

- fresh branch from current `main`
- bounded PRs only
- one decision-awareness slice per PR
- read-only interpretation first
- no persistence until a smaller decision contract is explicitly approved

## Recommended Step 2 Order

Suggested ladder:

1. design note and boundary lock
2. run interpretation schema draft
3. bounded classification/read signal slice
4. Mission Control signal rendering

Only after those are stable should any future guidance/control-plane work be considered.

## Final Classification

Step 2 is:

- not yet opened for implementation
- ready for bounded design work
- intentionally constrained to interpretation only

Short summary:

- Step 1 made proof consumption visible
- Step 2 should make proof consumption understandable
