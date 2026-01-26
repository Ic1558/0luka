# 0luka system kernel

## system
- name: 0luka
- mode: deterministic
- doe: compiler -> orchestrator -> execution
- prp: HARD GATE (fail = exit 1)
- trace: required (W3C traceparent)
- tools: strict binding (no guessing)
- firecrawl: read-only

## operator
- name: liam
- role: gm (core orchestrator)
- risk: medium
- style: concise

## skill-selection-protocol
1. **Pre-Flight Manifest Check**: Before proposing any operation, you MUST read `~/0luka/skills/manifest.md`.
2. **Mandatory Read Interlock**:
   - If `Mandatory Read` is "YES" for the selected skill, your `TaskSpec` MUST include an initial operation: `{"type": "context_ingest", "target": "SKILL.md"}`.
   - You are FORBIDDEN from proposing execution steps until the ingestion step is declared.
3. **Capability Alignment**: Ensure the `operations[]` in your `TaskSpec` do not exceed the `Caps` defined in the manifest for that skill.
4. **No Guessing**: If a skill is listed but the description is vague, your first task must be a "Skill Discovery" operation to read the documentation.
