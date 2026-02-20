# Governance Policies (01_01)

## 1. Boundary Manifesto (Core Rules)

- **Geometry Boundary:** All geometry must remain in deterministic tools (AutoCAD, SketchUp). LLMs are forbidden from generating or interpreting spatial data.
- **Execution Boundary:** All changes must follow: `Discovery -> Plan -> Dry-Run -> Verify -> Run`.
- **Lane Separation:** Deterministic (Human/CAD) vs. Semantic (LLM/Intent).

## 2. Agent Policies

- **Ghost Agent Prohibition:** No LaunchAgent shall refer to a non-existent file. All "inactive" agents must be marked as `.OBSOLETE` or `RETIRED`.
- **Truth Reporting (Mission Control v0.1):** Reports (incl. SYSTEM_HEALTH) must reflect real test/linter outcomes based on hard evidence in the repo or proof packs. If a state has not been proven or execution failed, the status MUST be 'UNKNOWN' or 'FAILING' (No guessing).
- **Authoritative Health definition:**
  - **Development Health:** Determined by **Unit Tests** (e.g., `core/verify/*.py`).
  - **Runtime Health:** Determined by **Proof Packs** (e.g., `observability/artifacts/proof_packs/*`).

## 3. Communication Style

- **Proactive Verification:** Agents must document success with evidence (logs, diffs, snapshots). Never claim success without a trail.
