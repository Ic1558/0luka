---
name: notebooklm_grounding
description: Ground lessons using NotebookLM MCP from failure/success evidence and export deterministic lesson summaries to observability/lessons. Use for postmortem distillation and retrieval-ready learning notes. Mandatory Read: YES
---

# NotebookLM Grounding

Mandatory Read: YES

## Workflow
1. Create or list notebook for current incident/topic.
2. Ingest failure logs, success logs, and verification artifacts.
3. Query NotebookLM for recurring failure causes and successful mitigations.
4. Export distilled lessons to `observability/lessons/<topic>.md`.

## Inputs
- Observability logs and proof artifacts.
- Prior lesson files in `observability/lessons/`.

## Outputs
- Markdown lesson summary under `observability/lessons/`.
- Deterministic headings: `Context`, `Failure Pattern`, `Mitigation`, `Constraint`, `Next Check`.

## Caps
- Read evidence artifacts.
- Query NotebookLM MCP.
- Produce advisory markdown.

## Forbidden
- No execution dispatch.
- No edits to `core/` or runtime policy.
- No auto-apply to task planner.
