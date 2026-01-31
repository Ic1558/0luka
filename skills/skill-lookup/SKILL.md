# Skill: Skill Lookup (The Registry)

---
name: skill-lookup
version: 1.0
category: meta
owner: gmx
sot: true

capabilities:
  filesystem:
    read: true
  process:
    exec: true

mandatory_read: YES
mandatory_sources:
  - "skills/"

output_contract:
  primary: "List of available skills with descriptions."
---

## 1. Identity
- **Role**: The Registry. I know who can do what.
- **Motto**: "Seek and you shall find."

## 2. Usage
```bash
# List all skills
zsh skills/skill-lookup/scripts/catalog.zsh

# Find specific capability
zsh skills/skill-lookup/scripts/catalog.zsh --find "deploy"
```
