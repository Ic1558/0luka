# OpenCode TODO: Core Architecture Deployment

**Full plan**: `core_architecture_phased.md` (same directory)

## Go/No-Go Decision

**Phase 1 NOW**: JSON/YAML contracts (universal readability)
**Phase 2.5 LATER**: Rust as SOT (after jobs contract proven)

**Current bottleneck**: No jobs endpoints + contract not authoritative
**Don't over-engineer** before basics work.

---

## Phase 1 Actions (NOW)

### 1. Create `ic1558/core` Repo
```bash
gh repo create ic1558/core --public \
  --description "Contracts, schemas, semantics (SOT)"
```

### 2. Create Structure
```
core/
├── VERSION              # "1.0.0"
├── COMPATIBILITY.md     # Promise to modules
├── contracts/v1/        # OpenAPI specs
├── schemas/v1/          # JSON schemas
└── semantics/           # Markdown docs
```

### 3. Write First Contract
- `contracts/v1/opal_api.openapi.yaml`
- Must include `/jobs` endpoint

### 4. Create `setup` Menu on MBP
```bash
# ~/.local/bin/setup
# Interactive menu for MBP → Mini control
```

### 5. Wire 0luka to Validate Against Core
- CI fetches core contracts
- Validates server matches spec

---

## Phase 2.5 Actions (LATER)

**When**: jobs contract + server match proven

1. Add `Cargo.toml` to core
2. Write Rust types with `#[derive(JsonSchema, ToSchema)]`
3. Auto-generate specs from Rust
4. CI regenerates on every push

---

## Key Principles
- ❌ No hard paths
- ✅ Use `CORE_CONTRACTS_URL` env var
- ✅ Phase 1: JSON/YAML (start simple)
- ✅ Phase 2.5: Rust (lock correctness)
