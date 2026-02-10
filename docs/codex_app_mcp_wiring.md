# Codex App MCP Wiring (Phase 15)

## Purpose
Wire Codex app to Skill OS inputs while preserving read/assist-only behavior.

## Required Preload
1. Read `skills/manifest.md`.
2. Resolve selected skills.
3. For any row with `Mandatory Read: YES`, load that skill's `SKILL.md` before action planning.

## Recommended Local MCPs
- NotebookLM MCP (for lesson grounding only).
- Local filesystem MCP (read-only for evidence and lessons).

## Wiring Notes
- Keep MCP permissions minimal and explicit.
- Do not grant execution paths from Skill OS docs.
- Preserve repo-relative paths in all references.

## Why Antigravity Is Not the OS
Antigravity is a developer/runtime tool. Skill OS is governance-level documentation and deterministic loading contract owned by core-brain. Skill OS must remain portable across tooling environments.

## Safety
- No auto-apply of lessons.
- No dispatcher/router invocation from Skill OS layer.
- Advisory output only.
