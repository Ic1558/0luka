# 0luka Architecture Invariants

## System Classification Invariant

0luka is a bounded Observability + Reasoning system.

The system interprets signals, classifies them, previews decisions, and stores decision memory but does not execute actions.

## Observability First Principle

All reasoning must originate from observable runtime signals.

No reasoning layer may bypass runtime observability.

## Signal Interpretation Invariant

Runtime signals must be interpreted before classification.

Interpretation creates a human-readable system state representation.

## Classifier Purity Rule

The classification layer must remain side-effect free.

Classifier output must never mutate system state.

## Decision Preview Constraint

Decision preview surfaces must remain read-only.

They exist only to expose reasoning results.

## Decision Persistence Boundary

Decision persistence stores reasoning outputs but must never trigger system actions.

Persistence must remain bounded.

## Control Plane Separation

Control-plane execution must remain separated from reasoning.

Reasoning layers must not execute actions.

## Frozen Canonical Boundary

repos/qs remains frozen canonical.

No architecture change may modify repos/qs.

## Knowledge Mirror Constraint

NotebookLM acts as a knowledge mirror of repository state.

The mirror must not mutate repository data.

## Governance Discipline

All architecture evolution must occur through bounded lanes and explicit PRs.

Implicit system mutation is forbidden.

## Evolution Safety Rule

Future evolution must never introduce system autonomy implicitly.

## Architecture Diagram

```text
Runtime
  ↓
Signals
  ↓
Interpretation
  ↓
Classification (dry-run)
  ↓
Decision Preview
  ↓
Decision Memory

Knowledge Mirror
  └─ NotebookLM publish

Boundary
  └─ repos/qs frozen canonical
```
