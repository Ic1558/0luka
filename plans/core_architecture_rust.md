# Plan: OS-Grade Multi-Module Architecture

## Vision

Design for **small-OS future** from day one:
- No hard paths
- No monorepo
- Modules = deployable/replaceable units
- Core = "kernel" (contracts/semantics)
- Everything else = userland modules

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

## Core Repo Structure (OS-Grade + Rust)

**Rust types = TRUE source of truth** → auto-generate specs

```
ic1558/core/
├── Cargo.toml                   # Rust workspace
├── VERSION                      # "1.0.0" - semver
├── COMPATIBILITY.md             # Promise to all modules
├── CHANGELOG.md                 # What changed per version
│
├── src/                         # Rust Source (TRUE SOT)
│   ├── lib.rs                   # Entry point
│   ├── types/
│   │   ├── mod.rs
│   │   ├── job.rs               # #[derive(JsonSchema, ToSchema)]
│   │   ├── artifact.rs
│   │   └── event.rs
│   ├── api/
│   │   ├── mod.rs
│   │   ├── opal.rs              # #[utoipa::path(...)]
│   │   └── registry.rs
│   └── semantics/
│       ├── mod.rs
│       └── job_lifecycle.rs     # State machine in code
│
├── generated/                   # Auto-generated (DO NOT EDIT)
│   ├── contracts/v1/
│   │   ├── opal_api.openapi.yaml
│   │   └── job_registry.openapi.yaml
│   ├── schemas/v1/
│   │   ├── job.schema.json
│   │   ├── artifact.schema.json
│   │   └── event.schema.json
│   └── latest -> v1
│
├── semantics/                   # Human-readable docs
│   ├── job_lifecycle.md         # Generated from Rust
│   ├── error_codes.md
│   └── event_ordering.md
│
├── tools/
│   ├── generate.sh              # cargo run --bin generate
│   ├── validate.sh
│   └── check_breaking.sh
│
└── .github/
    └── workflows/
        ├── generate.yaml        # Regenerate specs on push
        ├── release.yaml
        └── notify_modules.yaml
```

**Key Rust crates:**
- `schemars` - Generate JSON Schema from Rust types
- `utoipa` - Generate OpenAPI from Rust
- `strum` - Enum utilities for state machines

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

### Phase 3: Write Rust Types (TRUE SOT)

```rust
// src/types/job.rs
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, ToSchema)]
pub struct Job {
    pub id: String,
    pub status: JobStatus,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub executor: Option<String>,
    pub inputs_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, ToSchema)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
}
```

```rust
// src/api/opal.rs
use utoipa::{OpenApi, path};

#[utoipa::path(
    get,
    path = "/health",
    responses(
        (status = 200, description = "Service healthy")
    )
)]
pub async fn health() -> impl axum::response::IntoResponse {
    "ok"
}

#[derive(OpenApi)]
#[openapi(paths(health, create_job), components(schemas(Job, JobStatus)))]
pub struct OpalApi;
```

### Phase 4: Generate Specs

```bash
# tools/generate.sh
#!/bin/bash
cargo run --bin generate
# Outputs:
#   generated/contracts/v1/opal_api.openapi.yaml
#   generated/schemas/v1/job.schema.json
```

CI runs this on every push → specs always match Rust types.

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
| **Contract source** | **Hand-written YAML** | **Rust types → auto-generate** |
| **Type safety** | **Runtime errors** | **Compile-time guarantees** |
| **Small-OS ready** | **No** | **Rust = systems language** |

---

## Verification

1. `core` repo has VERSION, COMPATIBILITY.md, contracts/v1/
2. Modules use CORE_CONTRACTS_URL env var
3. CI validates module against core
4. `setup` menu works on MBP
5. No hard paths anywhere
