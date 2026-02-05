# Plan: OS-Grade Multi-Module Architecture

## Vision

Design for **small-OS future** from day one:
- No hard paths
- No monorepo
- Modules = deployable/replaceable units
- Core = "kernel" (contracts/semantics)
- Everything else = userland modules

---

## Phased Approach (Go/No-Go Decision)

### Phase 1 (NOW): JSON/YAML Contracts
- Core = contracts-only (JSON/YAML/Markdown)
- **Why**: Get system talking first, universal readability
- **Goal**: jobs contract + server match, authoritative spec

### Phase 2.5/3 (LATER): Rust as Source of Truth
- **When**: After jobs contract proven working
- **Why**: Lock correctness long-term, compile-time guarantees
- Rust structs → auto-generate OpenAPI/JSON Schema

**Current bottleneck**: No jobs endpoints + contract not authoritative yet
**Don't over-engineer** before basics work.

---

## Architecture (OS Thinking)

```
┌─────────────────────────────────────────────────────────────────┐
│                        ic1558/core                               │
│                    "The Kernel" (SOT)                            │
│                                                                  │
│   contracts/        ← API specs (like syscall table)            │
│   schemas/          ← Data structures (like ABI)                │
│   semantics/        ← Behavior rules (like POSIX spec)          │
│   COMPATIBILITY.md  ← Promise to modules                         │
│   VERSION           ← Semantic versioning                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Module Discovery    │
                    │   (env vars / config) │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  ic1558/0luka │      │ design-lane-  │      │    Future     │
│   (Executor)  │      │    macos      │      │   Modules     │
│               │      │    (UI)       │      │               │
│ Consumes core │      │ Consumes core │      │ Consumes core │
│ via URL/env   │      │ via URL/env   │      │ via URL/env   │
└───────────────┘      └───────────────┘      └───────────────┘
```

**Key principle**: Modules discover `core` via environment/config, never hard paths.

---

## Core Repo Structure

### Phase 1 (NOW): JSON/YAML Contracts

```
ic1558/core/
├── VERSION                      # "1.0.0" - semver
├── COMPATIBILITY.md             # Promise to all modules
├── CHANGELOG.md                 # What changed per version
│
├── contracts/                   # API Specifications (hand-written)
│   ├── v1/
│   │   ├── opal_api.openapi.yaml
│   │   └── job_registry.openapi.yaml
│   └── latest -> v1
│
├── schemas/                     # Data Structures
│   ├── v1/
│   │   ├── job.schema.json
│   │   ├── artifact.schema.json
│   │   └── event.schema.json
│   └── latest -> v1
│
├── semantics/                   # Behavior Rules (Markdown)
│   ├── job_lifecycle.md
│   ├── error_codes.md
│   └── event_ordering.md
│
├── tools/
│   ├── validate.sh
│   └── check_breaking.sh
│
└── .github/
    └── workflows/
        ├── release.yaml
        └── notify_modules.yaml
```

### Phase 2.5 (LATER): Rust as Source of Truth

**Add when**: jobs contract proven working + server matches spec

```
ic1558/core/
├── Cargo.toml                   # Add Rust workspace
├── src/                         # Rust Source (TRUE SOT)
│   ├── types/job.rs             # #[derive(JsonSchema, ToSchema)]
│   └── api/opal.rs              # #[utoipa::path(...)]
├── generated/                   # Auto-generated from Rust
│   └── contracts/v1/*.yaml
└── ...existing structure...
```

**Key Rust crates (future):**
- `schemars` - Generate JSON Schema from Rust types
- `utoipa` - Generate OpenAPI from Rust

---

## Versioning Rule

**Semantic Versioning for Contracts**

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| New optional field | MINOR | 1.0.0 → 1.1.0 |
| New endpoint | MINOR | 1.0.0 → 1.1.0 |
| Breaking change | MAJOR | 1.0.0 → 2.0.0 |
| Bug fix in spec | PATCH | 1.0.0 → 1.0.1 |

**Version in contracts:**
```yaml
# opal_api.openapi.yaml
openapi: 3.1.0
info:
  title: Opal API
  version: 1.0.0  # ← matches core VERSION
```

---

## Compatibility Promise

```markdown
# COMPATIBILITY.md

## Promise to Modules

1. **No breaking changes in MINOR/PATCH releases**
   - New fields are always optional
   - Existing endpoints never removed without MAJOR bump

2. **Deprecation policy**
   - Deprecated features marked in spec
   - Minimum 1 MAJOR version before removal
   - Migration guide provided

3. **Contract evolution strategy**
   - v1, v2, v3 directories coexist
   - Modules choose which version to consume
   - Old versions maintained for 2 MAJOR releases

4. **Discovery guarantee**
   - Modules NEVER hardcode paths
   - Use: CORE_CONTRACTS_URL environment variable
   - Or: config.yaml with contracts_url key
```

---

## Module Discovery (No Hard Paths)

**Modules discover core via:**

```bash
# Environment variable
export CORE_CONTRACTS_URL="https://raw.githubusercontent.com/ic1558/core/v1"

# Or local for development
export CORE_CONTRACTS_URL="file:///Users/icmini/repos/core"
```

**In module code:**
```swift
// Swift (design-lane-macos)
let coreURL = ProcessInfo.processInfo.environment["CORE_CONTRACTS_URL"]
    ?? "https://raw.githubusercontent.com/ic1558/core/latest"
```

```python
# Python (0luka)
import os
CORE_URL = os.environ.get("CORE_CONTRACTS_URL",
    "https://raw.githubusercontent.com/ic1558/core/latest")
```

---

## Module Registry (Future Ready)

When you need orchestration later, add manifest:

```yaml
# ic1558/ic-manifest/manifest.yaml (future)
version: "1.0"
core:
  repo: ic1558/core
  version: ">=1.0.0"

modules:
  executor:
    repo: ic1558/0luka
    requires_core: ">=1.0.0"
    ports: [7001]

  ui-macos:
    repo: ic1558/design-lane-macos
    requires_core: ">=1.0.0"
    depends_on: [executor]
```

This is **NOT a monorepo** - it's a **system manifest** (like a Linux distro).

---

## Implementation Steps

### Phase 1: Create `core` Repo

```bash
gh repo create ic1558/core --public \
  --description "Contracts, schemas, semantics (SOT for all modules)"
```

Initial structure:
```bash
mkdir -p contracts/v1 schemas/v1 semantics tools
echo "1.0.0" > VERSION
```

### Phase 2: Write COMPATIBILITY.md

Document the promise to all future modules.

### Phase 3: Write First Contract (JSON/YAML)

```yaml
# contracts/v1/opal_api.openapi.yaml
openapi: 3.1.0
info:
  title: Opal API
  version: 1.0.0
paths:
  /health:
    get:
      operationId: getHealth
      responses:
        '200':
          description: Service healthy
  /jobs:
    post:
      operationId: createJob
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateJobRequest'
      responses:
        '201':
          description: Job created
components:
  schemas:
    Job:
      type: object
      properties:
        id: { type: string }
        status: { type: string, enum: [pending, running, completed, failed] }
        created_at: { type: string, format: date-time }
```

### Phase 4 (Future): Migrate to Rust

**When**: jobs contract proven + server matches

```rust
// src/types/job.rs (FUTURE)
#[derive(JsonSchema, ToSchema)]
pub struct Job {
    pub id: String,
    pub status: JobStatus,
    pub created_at: DateTime<Utc>,
}
```

Then CI auto-generates YAML from Rust → specs always match code.

### Phase 4: Setup `setup` Menu on MBP

```bash
#!/bin/zsh
# ~/.local/bin/setup

echo "┌─────────────────────────────────────┐"
echo "│      MBP → Mini Control Panel       │"
echo "├─────────────────────────────────────┤"
echo "│  1) SSH to Mini (icmini)            │"
echo "│  2) Check Mini status               │"
echo "│  3) View API health (:7001)         │"
echo "│  4) View 0luka logs                 │"
echo "│  5) Fetch artifacts (safe)          │"
echo "│  q) Quit                            │"
echo "└─────────────────────────────────────┘"

read "choice?Select: "
case $choice in
  1) ssh macmini ;;
  2) ssh macmini "uptime && df -h ~ | tail -1" ;;
  3) curl -s http://100.77.94.44:7001/health | jq ;;
  4) ssh macmini "tail -50 ~/0luka/logs/latest.log" ;;
  5) rsync -av macmini:~/0luka/artifacts/ ~/0luka-artifacts/ ;;
  q) exit 0 ;;
esac
```

### Phase 5: Wire Modules to Core

Add CI validation in each module repo.

---

## Summary: What Makes This OS-Grade

| Feature | Traditional | OS-Grade (This Plan) |
|---------|-------------|----------------------|
| Path binding | Hard paths | Environment/config discovery |
| Dependencies | Implicit | Explicit version requirements |
| Breaking changes | Hope it works | Semantic versioning + policy |
| Module coupling | Direct imports | Contract-based |
| Future modules | Refactor needed | Plug-and-play |

### Phased Evolution

| Phase | Contract Source | Type Safety | When |
|-------|-----------------|-------------|------|
| **1 (NOW)** | Hand-written YAML/JSON | Runtime validation | Start here |
| **2.5 (LATER)** | Rust → auto-generate | Compile-time | After jobs contract proven |

---

## Verification

1. `core` repo has VERSION, COMPATIBILITY.md, contracts/v1/
2. Modules use CORE_CONTRACTS_URL env var
3. CI validates module against core
4. `setup` menu works on MBP
5. No hard paths anywhere
