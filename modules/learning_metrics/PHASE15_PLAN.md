# Phase 15 Plan: Skill OS

## Plan Summary
1. Define Skill OS SOT and chained-load contract in `skills/manifest.md`.
2. Add deterministic SKILL.md definitions for three Phase 15 skills.
3. Add MCP wiring guidance for Codex app usage.
4. Add verification for manifest parse and mandatory-read detection.
5. Run baseline health verification to ensure no regression.

## Deliverables
- `skills/manifest.md`
- `skills/notebooklm_grounding/SKILL.md`
- `skills/knowledge_recycling/SKILL.md`
- `skills/asset_fragment_manager/SKILL.md`
- `docs/codex_app_mcp_wiring.md`
- `core/verify/test_phase15_skill_os.py`

## Verification
- `python3 core/verify/test_phase15_skill_os.py`
- `python3 core/health.py --full`
