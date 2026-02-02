# 0luka STUDIO Lane - Specification

## 1. Overview
The **STUDIO Lane** is a lightweight, iterative execution environment designed for creative and AEC (Architecture, Engineering, Construction) tasks. It prioritizes speed and feedback loops over the forensic audit-trail requirements of the **SYSTEM Lane**.

### Core Differences
| Feature | SYSTEM Lane | STUDIO Lane |
| :--- | :--- | :--- |
| **Logic** | Code, Config, System State | Images, Renders, Visuals |
| **Contract** | `TaskSpec v2` (CLEC) | `PromptSpec v1` |
| **Verification** | Forensic (Vera) | Safety-only (Vera_Lite) |
| **Approval** | Multi-gate (GMX/Boss) | Optimistic / Auto-Pass (Safety) |
| **Output** | Evidence (Logs/Diffs) | Artifacts (Images/PDFs) |

---

## 2. Directory Structure (Module Architecture)

New features are implemented as **Modules** to keep the 0luka Core immutable.

```text
modules/studio/
├── manifest.yaml           # Module definition
├── schemas/                # Contract schemas (YAML)
├── connector/              # CLI interface (studio.zsh)
├── runtime/                # Executor logic (Python)
├── outputs/                # Artifact storage
└── rfc/                    # Documentation
```

---

## 3. Contracts (V1)

### A. PromptSpec v1 (Request)
Dropped into `interface/inbox/` as `module_request_<id>.yaml`.
- **Kind**: `pdf`, `image`, `plan`, `text`.
- **Input**: Relative paths under allowed scopes.
- **Goal**: Natural language intent.
- **Constraints**: Style tags, aspect ratio, resolution.

### B. OutputBundle v1 (Response)
Written to `modules/studio/outputs/<artifact_id>/output_bundle.yaml`.
- **Status**: SUCCESS / FAILED / PARTIAL.
- **Outputs**: List of artifact paths and labels.
- **Safety**: Flag for verified path compliance.

---

## 4. Governance & Safety

### 3. Safety Model: "Fail-Closed"
We employ a strictly scoped safety model designated **Vera_Lite**.

#### A. Path Boundary (Allowlist)
The Executor CANNOT write to `core/` or `system/`. It is jailed to:
1.  `projects/**` (User creative workspaces)
2.  `assets/**` (Input assets)
3.  `renders/**` (Intermediate renders)
4.  `exports/**` (Final outputs)
5.  `sandbox/**` (Experimental scratchpad)
6.  `modules/studio/outputs/**` (Structural logs)

**Hard Deny:** (Takes precedence)
*   `0luka/runtime/**` (System Runtime)
*   `system/**` (System Configuration)
*   `tools/**` (Core Tools)
*   `governance/**` (Policy Docs)
*   `.env*`, `*.key`, `*.pem`, `*.p12`, `*.kdbx`, `id_rsa*` (Credentials)

#### B. Secret Scanning
Vera in STUDIO mode only performs **Safety Scans**:
1. Path boundary check.
2. Secret detection (Regex).
*Aesthetics/Taste are never judged.*
