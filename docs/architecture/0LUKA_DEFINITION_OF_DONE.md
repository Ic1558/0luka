# 0luka Definition of Done

## Purpose

This document defines what "done" means for the 0luka system.

It establishes completion criteria at the system, phase, PR, observability, governance, and operational-proof levels.

## System-Level DoD

A healthy mainline must satisfy all of the following:

- the system remains within its current architectural boundary
- mainline remains clean and bounded
- frozen canonical boundaries remain untouched unless explicitly reopened
- observability and reasoning layers remain intact
- no implicit control-plane behavior is introduced

## Phase-Level DoD

An architectural phase is complete when:

- its intended capability is implemented or documented as designed
- its boundaries are explicit
- its relationship to earlier and later phases is documented
- it does not leak into adjacent phases implicitly
- it is verified against the current architecture plateau

## PR-Level DoD

A pull request is ready to merge when:

- scope is bounded and coherent
- only intended files are changed
- required verification has been run
- governance expectations are satisfied
- the change does not violate frozen boundaries or architectural rules

## Observability Requirements

System state must always remain observable.

Changes must preserve the ability to inspect runtime state, interpreted state, and bounded decision state through explicit observability surfaces.

## Governance Requirements

All changes must pass governance gates.

This includes:

- bounded lane discipline
- architectural consistency
- frozen boundary protection
- documented rationale for meaningful architectural changes

## Operational Proof Requirement

Operationally meaningful changes must carry proof expectations appropriate to their scope.

Proof may include:

- targeted verification results
- architecture documentation
- bounded runtime evidence
- explicit confirmation that no forbidden surfaces were changed

## Final Statement

A change is considered complete only when it satisfies the Definition of Done at all applicable levels.
