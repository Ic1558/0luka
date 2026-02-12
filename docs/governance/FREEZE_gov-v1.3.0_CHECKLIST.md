# Governance Freeze Decision + Canonical Checklist (`gov-v1.3.0`)

## 1) Freeze Decision

Based on current governance status:

- ✅ Auto-adaptive governance router merged to `main`
- ✅ CI green
- ✅ Strict DoD passing target (`DESIGNED:1`, `PROVEN:15`)
- ✅ Stale post-merge artifact removed
- ❌ Tag not created yet
- ❌ Canonical freeze evidence bundle not produced yet

### Governance conclusion

This change affects the governance control plane (`R3` + `R2` tooling), so it should be treated as a **Governance Minor Version** freeze.

**Recommended tag:** `gov-v1.3.0`

---

## 2) Mandatory Preconditions (Fail-Closed)

Freeze is allowed only if all checks pass:

### (A) Topology integrity

- `git branch --show-current` returns `main`
- `git remote -v` contains `origin`

### (B) Lock integrity

```bash
python3 tools/ops/governance_file_lock.py --verify-manifest --json
```

Must report `ok: true`.

### (C) Strict DoD integrity

```bash
LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --all --json
```

Must satisfy governance target:

- `DESIGNED: 1`
- `PROVEN: 15`

### (D) Clean tree

```bash
git status --porcelain
```

Must be empty.

### (E) CI integrity on `main`

All required checks must be green on `main`:

- `governance-file-lock`
- `phase-growth-guard`
- `auto-governor-router`

If any precondition fails, **STOP**.

---

## 3) Canonical Freeze Script Flow (Mac mini only)

Run only in canonical repo path:

```bash
cd /Users/icmini/0luka || exit 1
set -euo pipefail

echo "== PRECHECK =="

git checkout main
git pull --ff-only

test -z "$(git status --porcelain)" || { echo "STOP: dirty tree"; exit 1; }

python3 tools/ops/governance_file_lock.py --verify-manifest --json

LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --all --json

echo "== CREATE TAG =="

git tag gov-v1.3.0
git push origin gov-v1.3.0

echo "== VERIFY TAG =="

git show gov-v1.3.0 --no-patch --oneline

echo "OK: gov-v1.3.0 frozen"
```

---

## 4) Immediate Post-Freeze Actions

1. Create `docs/governance/VERSION_gov-v1.3.0.md`.
2. Record:
   - `HEAD` SHA
   - `verdict_counts`
   - lock hash summary
3. Commit the evidence file.
4. Push to `origin`.

---

## 5) Governance Risk Assessment

| Risk | Status |
|---|---|
| Governance weakening | None |
| Router regression | Covered by 25 tests |
| Contract mismatch | Covered by 4 tests |
| Lock hash drift | Regenerated + verified |
| Silent branch drift | None observed |

---

## 6) Strategic State

Current system position:

- Governance stable
- Enforcement deterministic
- CI enforced
- Ready for version freeze

Expected freeze outcomes:

- Governance ABI lock
- Enforcement behavior snapshot
- Audit anchor for future changes
