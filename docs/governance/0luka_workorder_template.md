# 0luka Canonical Work Order Template (SOT Rev1.1)

---
**SOT AUTHORITY**

- **Blueprint Reference**: Blueprint Rev1.3 (PPR/DoD/AgentTeams)
- **Governance Version**: v1.1-hardened
- **Enforced From**: 2026-02-12

---

<!--
    STRICT COMPLIANCE RULES:
    1. NO NARRATIVE outside the defined fenced blocks.
    2. ONE WORK ORDER = ONE LANE = ONE OBJECTIVE. No combined scopes.
    3. NO HALLUCINATIONS. All file paths and outputs must be real.
    4. BRANCH PREFIX must strictly follow the Branch Namespace Policy (lane/intent only).
    5. EXIT-CODE CONTRACT: 0=PROVEN, 2=PARTIAL, 3=DESIGNED, 4=ERROR.
-->

## 1. ROLE

[Specify the Agent Persona: GMX (Governance), Codex (Runtime), Liam (Architect), or Lisa (Executor)]

## 2. OBJECTIVE

[Single, clear sentence defining the primary goal. Must be measurable.]

## 3. SCOPE (STRICT)

- [List specific files to create or modify]
- [List specific tests to run]
- [Explicitly exclude out-of-scope items]

## Branch Namespace Policy (Universal)

### ✅ Allowed branch namespaces (lane/intent only)

Branch name MUST start with exactly one of these lane prefixes:

- `feat/`
- `fix/`
- `docs/`
- `ops/`
- `governance/`
- `tooling/`
- `runtime/`

### ❌ Forbidden prefixes (agent-name prefixes)

Agent-name prefixes are FORBIDDEN and must never be used as branch namespaces, including but not limited to:

- `codex/`
- `gmx/`
- `lisa/`
- `cole/`

Reason: branches represent *work lane/intent*, not *which agent* created them.

### ✅ Validator (hard constraint)

Branch name MUST match this regex:

`^(feat|fix|docs|ops|governance|tooling|runtime)\/[a-z0-9][a-z0-9._-]*$`

Examples:

- ✅ `tooling/dod-briefing-contract`
- ✅ `governance/branch-namespace-policy`
- ❌ `codex/docs-governance-change-phase3-1-5`
- ❌ `gmx/some-change`

## 4. CONSTRAINTS

- [Constraint 1: Branch must rigidly match the regex validator in Branch Namespace Policy]
- [Constraint 2: Must preserve Exit-Code contract (0/2/3/4)]
- [Constraint 3: All outputs must be fenced and paste-ready]

## 5. IMPLEMENTATION REQUIREMENTS

- [Requirement 1: Logic/Step detail]
- [Requirement 2: Error handling (Fail-Closed)]

## 6. ACCEPTANCE CRITERIA

- [ ] [Criterion 1: Verification command passes]
- [ ] [Criterion 2: Artifact exists at path]

## 7. EVIDENCE REQUIRED (MANDATORY)

1. `git branch` name.
2. `git diff --stat` output.
3. Test/Verify command execution + full output.
4. `git status` (must be clean).

## 8. OUTPUT FORMAT

- **Branch**: [prefix/branch-name]
- **Evidence**: Fenced code blocks only.
- **Narrative**: Zero explanatory prose outside required fields.

<!-- END SOT TEMPLATE -->
