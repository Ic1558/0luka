# Skill: Theme Factory (Normalized)

---
name: theme-factory
version: 1
category: design
owner: 0luka/design-adapter
sot: true
mandatory_read: NO
capabilities:
  filesystem: read
  process: denied
  network: denied
scope:
  - "~/0luka"
  - "~/ai-skills/design/theme-factory"
---

## 1. Identity
- **Role**: Deterministic Theme Application Engine
- **Purpose**:
  - Apply predefined color/font themes to documentation or artifacts on demand.
  - Provide a strict mapping of theme IDs to CSS/Design tokens.

## 2. Contracts (Deterministic)

### Input Contract (JSON)
```json
{
  "task_id": "required (string)",
  "artifact_path": "required (absolute path to target file/dir)",
  "theme_id": "required (e.g., 'ocean_depths', 'midnight_galaxy')",
  "mode": "optional (default: 'apply', options: 'apply'|'preview')"
}
```

### Output Contract (JSON)
```json
{
  "status": "ok|error",
  "summary": "Applied theme <theme_id> to <artifact_path>",
  "paths": {
    "artifact": "/absolute/path/to/modified_artifact"
  },
  "evidence": {
    "theme_id": "ocean_depths",
    "timestamp": "ISO-8601"
  }
}
```

## 3. Constraints (Fail-Closed)
- **Non-Interactive**: Never ask the user to choose a theme. Input `theme_id` must be provided by the Router/Planner.
- **Read-Only**: Can read theme definitions from `~/ai-skills/design/theme-factory/themes/`.
- **Write Scope**: Can only modify the specified `artifact_path`.
- **Fail Fast**: If `theme_id` is unknown, return error immediately.

## 4. Deterministic Execution Steps
1. **Validate**: Check `artifact_path` exists and `theme_id` is in the allowed list.
2. **Resolve**: Locate theme definition file in `~/ai-skills/design/theme-factory/themes/`.
3. **Execute**: Apply design tokens/CSS to the artifact content.
4. **Verify**: Confirm file was verified/written.
5. **Report**: Return JSON status.

## 5. Verification & Evidence
- **Pre-check**: `artifact_path` must be writable.
- **Post-check**: File mtime updated.

## 6. Router Integration
- **Call When**: Intent is `APPLY_THEME` or `STYLE_DOC`.
- **Upstream Must Decide**: The `theme_id`. (Router/Planner must pick based on user request or default).
- **Skill Never Decides**: Which theme looks "better".

## 7. Failure Modes
- `MISSING_INPUT`: `theme_id` or `artifact_path` missing.
- `UNKNOWN_THEME`: `theme_id` does not match known inventory.
- `FILE_NOT_FOUND`: Target artifact does not exist.
