## Phase
- [ ] `Phase 1A`
- [ ] `Phase 1B`
- [ ] `Phase 1C`
- [ ] `Phase 1D`
- [ ] `Phase 1E`
- [ ] `Other`:

## Scope (Allowed Files)
List exact paths changed by this PR.

```text
- 
```

## Explicit Non-Goals
List what this PR must NOT change.

```text
- 
```

## Contract Invariants
- [ ] Fail-closed behavior preserved
- [ ] No hard paths in payloads/artifacts (`/Users/`, `file:///Users`, `C:\\Users\\`)
- [ ] No cross-phase wiring outside declared phase scope
- [ ] No new runtime dependencies

## Verification (Evidence-Only)
Paste exact commands and outputs used to verify.

```bash
# compile / tests / proof commands
```

## Scope Lock Gate (Required)
- [ ] `git diff --name-only origin/main...HEAD` matches declared scope only
- [ ] Reviewer confirmed no extra files outside `Allowed Files`
- [ ] If scope mismatch: PR rejected

## Rollback
Provide safe rollback command(s).

```bash
# example
# git revert <commit_sha>
```
