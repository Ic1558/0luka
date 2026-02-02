---
spec_name: s4_feedback_loop
version: 1.0.0
status: DRAFT
author: GMX
---

# S4: Visual Logic Feedback Loop

This spec defines the "Self-Correction" phase of the AEC Pipeline.
**Goal:** Enable the Studio to audit its own output (Render) against the input (Plan + Brief) to detect drift.

## 1. Core Logic: The "Triangle of Truth"

The Feedback Loop compares three artifacts:
1.  **Truth (A):** The Clean Plan (S1). "Structural Truth"
2.  **Intent (B):** The Scene Brief (S2). "Semantic Truth"
3.  **Output (C):** The Draft Render (S3). "The Artifact"

**The Check:** `Actionable_Drift = (C vs A) + (C vs B)`

## 2. Check Types

### A. Structural Alignment (C vs A)
*   **Method:** Edge detection / Overlay comparison.
*   **Checks:**
    *   Do walls align?
    *   Are windows/doors in approx correct positions?
    *   Did the room shape distort?

### B. Semantic Drift (C vs B)
*   **Method:** VLM Analysis (FastVLM).
*   **Checks:**
    *   Brief: "Oak floor" -> Render: "Carpet" (FAIL)
    *   Brief: "Morning light" -> Render: "Night" (FAIL)
    *   Brief: "Modern" -> Render: "Baroque" (FAIL)

## 3. Output Schema: `feedback_report_v1`

Every run produces a report, not just a boolean pass/fail.

```yaml
schema: feedback_report_v1
target_artifact: art_xxx
structural_score: 0.85  # 0.0-1.0
semantic_score: 0.92
issues:
  - type: structural
    severity: high
    description: "North wall missing window opening."
  - type: semantic
    severity: low
    description: "Floor tone lighter than 'dark oak' request."
suggestion: "Re-run with ControlNet weight 0.8 for structure."
```

## 4. Governance
*   **Studio Lane Only**: Feedback reports stay in Studio.
*   **Advisory Only**: The system CANNOT auto-delete renders. It only tags them.
*   **Promotion Impact**: High-drift renders should be flagged during Human Review.
