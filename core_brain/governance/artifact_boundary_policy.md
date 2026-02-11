# 0luka Artifact Boundary Policy

## Principle: Source ≠ Artifact

**Source (git tracked):**
- Code (`*.py`, `*.zsh`, `*.ts`)
- Contracts (`*.yaml`, `*.json` schemas)
- Documentation (`*.md`)
- Config templates (`.env.example`)

**Artifacts (NEVER git tracked):**
- Runtime logs (`*.log`, `*.tracev3`)
- Session dumps (`session-*.md`)
- Trace/debug outputs (`*.dump`, `*.core`)
- Generated reports (`reports/`)
- Staging/temp (`staging/`, `runtime/`)

---

## Directory Contract

| Directory | Type | Git? | Retention |
|:---|:---|:---:|:---|
| `core/` | Source | ✅ | Forever |
| `tools/` | Source | ✅ | Forever |
| `observability/artifacts/` | Artifact | ❌ | 7 days |
| `staging/` | Artifact | ❌ | 24 hours |
| `runtime/logs/` | Artifact | ❌ | 3 days |
| `g/` | Ephemeral | ❌ | Session |

---

## Enforcement

1. **`.gitignore`** — Hard-blocks artifact dirs
2. **`.githooks/pre-commit`** — Blocks files >10MB
3. **Rotation script** — `tools/ops/rotate_logs.zsh`

---

## Why This Matters

Without boundaries:
- Logs creep into repo
- Git history bloats
- Push fails at 100MB+
- Recovery requires `git filter-repo`

**Prevention > Cleanup**
