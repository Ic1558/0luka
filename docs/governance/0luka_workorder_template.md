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
    4. BRANCH PREFIX must follow: feat/, fix/, chore/, codex/, or gmx/.
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

## 4. CONSTRAINTS
- [Constraint 1: Branch must be prefixed with feat|fix|chore|codex|gmx]
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
