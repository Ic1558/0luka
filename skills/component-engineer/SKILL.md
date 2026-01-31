# Skill: <Skill Name>

---
name: component-engineer
version: 1
category: <dev|ops|design|enterprise|security>
owner: <team/agent>
sot: true
mandatory_read: <YES|NO>
capabilities:
  filesystem: <read|write|rw|denied>
  process: <exec|denied>
  network: <denied|scoped>
scope:
  - "~/0luka"
  - "~/ai-skills"
---

## 1. Identity
- **Role**: <1-line strict role definition>
- **Purpose**:
  - <Bullet 1>
  - <Bullet 2>

## 2. Contracts (Deterministic)

### Input Contract (JSON)
```json
{
  "task_id": "required (string)",
  "field_1": "required (type)",
  "field_2": "optional (default: <val>)"
}
```

### Output Contract (JSON)
```json
{
  "status": "ok|error|skipped",
  "summary": "Brief description of result",
  "paths": {
    "output_key": "/absolute/path/to/result"
  },
  "evidence": {
    "key": "value"
  }
}
```

## 3. Constraints (Fail-Closed)
- **Non-Interactive**: No prompts, no waiting for user input.
- **Scope**: Must operate within defined filesystem scope.
- **Network**: <Denied or Whitelisted only>
- **Error Handling**: Fail fast on missing input or violation.

## 4. Deterministic Execution Steps
1. **Validate**: Check input schema and constraints.
2. **Execute**: Perform the core operation mechanically.
3. **Verify**: Check output integrity (file exists, syntax valid).
4. **Report**: Return structured JSON output.

## 5. Verification & Evidence
- **Pre-check**: Ensure required resources exist.
- **Post-check**: Verify artifact creation/modification.

## 6. Router Integration
- **Call When**: <Specific Intent / Condition>
- **Upstream Must Decide**: <List of parameters upstream must provide>
- **Skill Never Decides**: <List of ambiguous decisions skill avoids>

## 7. Failure Modes
- `MISSING_INPUT`: Required fields absent.
- `OUT_OF_SCOPE_PATH`: Target path not in allowlist.
- `CAPABILITY_DENIED`: Attempted forbidden action.
- `VERIFY_FAILED`: Output validation failed.
