---
name: knowledge_recycling
description: Convert incidents into reusable lessons with a deterministic Failure -> Lesson -> Constraint/Heuristic pipeline. Use when preparing future-safe planning context. Mandatory Read: YES
---

# Knowledge Recycling

Mandatory Read: YES

## Pattern
Failure -> Lesson -> Constraint/Heuristic

## Lesson Schema
- `lesson_id`
- `source_ref`
- `failure_signature`
- `constraint`
- `heuristic`
- `confidence`
- `reuse_scope`

## Storage
- Primary: `observability/lessons/*.md`
- Index references: include absolute-safe repo-relative paths only.

## Referencing Rule
- Future tasks may reference lessons.
- Lessons are advisory only and must never auto-mutate policy/runtime.

## Caps
- Summarize incidents.
- Create reusable lesson entries.
- Link lessons to verification evidence.

## Forbidden
- No dispatcher/router/executor calls.
- No policy auto-apply.
- No hidden side effects.
