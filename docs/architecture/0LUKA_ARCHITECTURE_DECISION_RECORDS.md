# 0luka Architecture Decision Records

## Purpose

ADRs document significant architectural decisions made during the evolution of 0luka.

ADRs allow maintainers to understand:

- why a decision was made
- what alternatives were considered
- what constraints existed at the time

## ADR Storage Location

The ADR directory is:

`docs/architecture/adr/`

Each ADR file must follow the naming pattern:

`ADR-XXXX-title.md`

Example:

`ADR-0001-observability-first-architecture.md`

## ADR Structure

The standard ADR template is:

- Title
- Status
- Context
- Decision
- Consequences
- Alternatives Considered

## ADR Lifecycle

- Proposed
- Accepted
- Superseded
- Deprecated

## ADR Reference Rule

ADRs may be referenced from:

- system topology documents
- evolution roadmap
- architecture invariants

## Initial ADR Index

- ADR-0001 — Observability-First Architecture
- ADR-0002 — Interpreted Observability Model
- ADR-0003 — Dry-Run Classification Design
- ADR-0004 — Read-Only Decision Preview
- ADR-0005 — Bounded Decision Persistence
- ADR-0006 — Frozen Canonical Boundary (`repos/qs`)
- ADR-0007 — Knowledge Mirror via NotebookLM

These ADRs may be written later.

## Governance Rule

Architectural decisions affecting system behavior must be documented as ADRs.

## Architecture Safety Statement

All major architecture changes must be documented through ADRs before implementation.

## Example ADR Diagram

```text
Architecture Decision
        ↓
 ADR Document Created
        ↓
 Governance Review
        ↓
 Implementation PR
```
