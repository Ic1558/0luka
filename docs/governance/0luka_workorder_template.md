# 0luka Canonical Work Order Template (SOT)

<!--
    USAGE: Copy this template exactly. Fill only the bracketed sections.
    DO NOT add narrative outside these sections.
    DO NOT combine multiple unrelated tasks in one Work Order.
-->

## 1. ROLE
[Specify the Agent Persona: GMX (Governance), Codex (Runtime), Liam (Architect), or Lisa (Executor)]

## 2. OBJECTIVE
[Single, clear sentence defining the primary goal. Must be measurable.]

## 3. SCOPE (STRICT)
- [List specific files to create or modify]
- [List specific tests to run]
- [Explicitly exclude out-of-scope items]
- [No "refactor everything" or "fix all bugs" scope allowed]

## 4. CONSTRAINTS
- [Constraint 1: e.g., No runtime changes allowed]
- [Constraint 2: e.g., Must follow SOT Blueprint Rev1.3]
- [Constraint 3: e.g., Python 3.12+ only]
- [Constraint 4: e.g., Use specific library versions]

## 5. IMPLEMENTATION REQUIREMENTS
- [Requirement 1: Detailed step or logic]
- [Requirement 2: Specific function names or signatures]
- [Requirement 3: Error handling strategy (fail-fast vs fail-open)]
- [Requirement 4: Logging/Telemetry format]

## 6. ACCEPTANCE CRITERIA
- [ ] [Criterion 1: File X exists and matches spec]
- [ ] [Criterion 2: Test Y passes with exit code 0]
- [ ] [Criterion 3: Linter passes with no errors]
- [ ] [Criterion 4: Evidence Z is generated]

## 7. EVIDENCE REQUIRED (MANDATORY)
1. `git branch` name used.
2. `git diff --stat` or relevant diff chunks.
3. Command output for verification tests (full stdout/stderr).
4. `git status` showing clean state after work.

## 8. OUTPUT FORMAT
- **Branch**: [feature/branch-name]
- **PR Description**: Short summary of changes.
- **Evidence**: Fenced code blocks only.
- **Narrative**: Minimal. "Done" or "Failed" is sufficient. 
- **No hallucinations**: Do not invent file paths or outputs.

<!-- END TEMPLATE -->
