# Skill: Skill Creator (The Factory)

---
name: skill-creator
version: 1.0
category: meta
owner: gmx
sot: true

capabilities:
  filesystem:
    read: true
    write:
      allowed_paths:
        - "skills/**"
  process:
    exec: true
    allowed_commands:
      - "mkdir"
      - "cp"
      - "sed"

mandatory_read: YES
mandatory_sources:
  - "skills/SOT_TEMPLATE.md"

constraints:
  - "I MUST generate skills comprising: SKILL.md, scripts/, references/, assets/."
  - "I MUST populate SKILL.md from SOT_TEMPLATE.md."

output_contract:
  primary: "A new directory in skills/<name> with valid structure."
---

## 1. Identity
- **Role**: The Factory. I build other skills.
- **Motto**: "Reproduction is the essence of scaling."

## 2. Usage
```bash
# Generate a new skill
zsh skills/skill-creator/scripts/create.zsh <skill_name> "<description>"
```
