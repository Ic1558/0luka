# 0luka Architecture Guardrails

## Purpose

These guardrails exist to prevent architecture drift and protect the bounded reasoning model of the 0luka system.

## Current System Boundary

The current system includes:

- Runtime signals
- Interpreted observability
- Dry-run classification
- Decision preview (read-only)
- Decision persistence (bounded)
- Knowledge mirror

## Forbidden Changes

The following changes must NOT occur without explicit architecture approval:

- introducing control-plane execution
- introducing automated remediation
- introducing artifact mutation
- bypassing observability layers
- introducing hidden side-effects in classifier logic
- modifying frozen canonical boundaries
- modifying repos/qs

## Allowed Changes

The following changes are currently acceptable:

- documentation improvements
- observability enhancements
- read-model improvements
- classifier analysis improvements
- decision preview visualization improvements
- bounded decision persistence improvements

## Frozen Canonical Boundary

repos/qs remains frozen canonical.

## Governance Model

Architecture changes must occur via:

- bounded PR lanes
- explicit architecture documentation
- maintainer review

## CI Enforcement Philosophy

CI should reject PRs that:

- violate architectural invariants
- introduce side effects in reasoning layers
- modify frozen boundaries

## Architectural Safety Statement

0luka must evolve through bounded architecture lanes and must never introduce control-plane execution implicitly.

## Minimal Architecture Diagram

```text
Runtime
  ↓
Signals
  ↓
Interpretation
  ↓
Classification
  ↓
Decision Preview
  ↓
Decision Memory

Knowledge Mirror
  └─ NotebookLM publish

Boundary
  └─ repos/qs frozen canonical
```
