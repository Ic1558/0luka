# 0luka Skill Manifest (SOT)

This file is the single source of truth for Skill OS loading order and constraints.

## Chained Load Contract
1. Read this `skills/manifest.md` before any skill-backed execution planning.
2. For each selected skill with `Mandatory Read: YES`, ingest its `SKILL.md` before proposing steps.
3. Enforce caps and forbidden actions from manifest and each `SKILL.md`.
4. Skills in this manifest are read/assist only unless explicitly upgraded by governance.

## Core-Brain Owned Skills (Phase 15)

| skill_id | purpose | Mandatory Read | MCPs used | Inputs | Outputs | Caps | Forbidden actions |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `notebooklm_grounding` | Distill lessons from success/failure artifacts using NotebookLM context grounding only. | YES | NotebookLM MCP | Failure logs, success logs, verification notes | `observability/lessons/*.md` | Create/list notebooks, ingest artifacts, query lessons, export distilled summary | Execute tasks, modify `core/`, mutate policy/runtime state |
| `knowledge_recycling` | Convert failures into reusable lessons, constraints, and heuristics for future planning. | YES | Local FS MCP (read-only) | Incident logs, postmortems, prior lessons | Structured lesson entries + cross-reference map | Normalize lessons, classify confidence, map references | Auto-apply policy, direct execution, dispatcher/router calls |
| `asset_fragment_manager` | Reuse deterministic small utilities/fragments with import-only discipline. | NO | Local FS MCP (read-only) | Existing utility fragments, helper snippets | Suggested imports and usage notes | Locate, validate, and suggest deterministic fragments | Mutate source fragments, execute external commands, auto-rewrite core |

## Legacy Catalog (Compatibility)

The legacy catalog remains available for backward compatibility. Phase 15 does not change those skills.

| Skill Name | Mandatory Read |
| :--- | :---: |
| `development` | YES |
| `design` | NO |
| `document-processing` | NO |
| `enterprise` | NO |
| `scripts` | NO |
| `context7` | NO |
| `theme-factory` | NO |
| `tailwind-css-expert` | NO |
| `component-engineer` | NO |
