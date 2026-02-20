# Governance Policies (01_01)

## 1. Boundary Manifesto (Core Rules)

- **Geometry Boundary:** All geometry must remain in deterministic tools (AutoCAD, SketchUp). LLMs are forbidden from generating or interpreting spatial data.
- **Execution Boundary:** All changes must follow: `Discovery -> Plan -> Dry-Run -> Verify -> Run`.
- **Lane Separation:** Deterministic (Human/CAD) vs. Semantic (LLM/Intent).

## 2. Agent Policies

- **Ghost Agent Prohibition:** No LaunchAgent shall refer to a non-existent file. All "inactive" agents must be marked as `.OBSOLETE` or `RETIRED`.
- **Linter Enforcement:** No PR can be merged without a passing linter state. Linter errors must be resolved or explicitly whitelisted via policy.

## 3. Communication Style

- **Proactive Verification:** Agents must document success with evidence (logs, diffs, snapshots). Never claim success without a trail.
