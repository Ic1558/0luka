# 0luka Studio: Hybrid Architecture Report
**Date:** 2026-02-02
**Status:** Phase 6 Complete (Operational)

## 1. The Concept: "Hybrid Creative Studio" 🎨 + ☁️

We have evolved the 0luka Studio from a simple local file processor into a **Hybrid Creative Engine**.

*   **The Problem:** Creative work requires both "High-Level Thinking" (Brainstorming, Logic Flow) and "Low-Level Production" (File conversion, Banner making, Formatting). Doing everything locally is limiting; doing everything in the cloud is slow and disjointed.
*   **The Solution:** A **Bi-Modal Architecture**:
    1.  **Cloud Brain (Google Opal)**: Acts as the "Creative Director". It handles logic, drafting, and complex decision-making via its visual node editor.
    2.  **Local Hands (0luka Studio)**: Acts as the "Production House". It handles reliable file processing (PDFs, Images), strict formatting, and asset management.
    3.  **The Bridge (Opal Hybrid Lane)**: A trusted, autonomous channel that connects the two.

---

## 2. What We Have Done (Implementation Log)

### ✅ Phase 4.2: Local Production Engines
We built the "Hands" of the system—three reliable Python engines to process raw files into usable assets.
*   **PDF → Images**: Converts architectural plans to high-res PNGs for preview.
*   **Image → Banner**: Automatically composites 16:9 updates with blurred backgrounds and typography.
*   **PDF → Summary**: Extracts key text and bullets into an interactive HTML dashboard.
*   **Status**: **VERIFIED** (All engines producing real artifacts).

### ✅ Phase 4.3: Visual Logic Hooks
We mapped the "Brain" of the system—identifying how to talk to Google Opal programmatically.
*   **Discovery**: Mapped Key UI Selectors (`textarea[placeholder="Edit these steps"]`).
*   **Recipe**: Created `opal_guide.md` to standardize how agents interact with the Opal Editor.
*   **Self-Test**: Verified we can find specific nodes (e.g., "Generate Draft Image") via browser automation.

### ✅ Phase 6: The Opal Hybrid Lane (New!)
We built the "Bridge"—a dedicated trusted pipeline for autonomous execution.
*   **Dedicated Lane**: `modules/opal/` created to separate "trusted cloud tasks" from "untrusted local inputs".
*   **Zero-Wait Execution**: Implemented `fast-track` policy. Unlike Studio tasks that wait for user confirmation, Opal tasks run *immediately*.
*   **Autonomous Driver**: Installed **Playwright** and created `opal_driver.py`. This script launches a browser, logs in (via user profile), and executes Opal edits without human intervention.
*   **Connector**: `opal.zsh` CLI tool to unified control: `opal run <url> <task>`.

---

## 3. Key Components & Edits

| Component | File Path | Role | Status |
| :--- | :--- | :--- | :--- |
| **Studio Connector** | `tools/studio.zsh` | Main CLI. Updated to support `opal` commands and URLs. | 🟢 Active |
| **Runtime Executor** | `modules/studio/runtime/executor.py` | Dispatcher. Logic added to route `opal` requests to manifests. | 🟢 Active |
| **Opal Driver** | `modules/opal/agent/opal_driver.py` | **The Robot**. A Python/Playwright script that physically drives the browser. | 🟢 Installed |
| **Opal Connector** | `modules/opal/connector/opal.zsh` | **The Trigger**. Allows "Fire and Forget" automation commands. | 🟢 Active |

## 4. How It Works Now

1.  **You Request**: `studio opal "https://opal.google/..." "Add a weather node"`
2.  **System Routes**: Recognizes it's a Cloud Task -> Sends to Opal Lane.
3.  **Bridge Executes**: `opal_driver.py` wakes up -> Opens Chrome -> Types into Opal -> clicks "Send".
4.  **Result Saved**: Evidence (Screenshots) is saved to `modules/opal/inbox`.
5.  **Handoff**: Artifacts can be passed back to Studio for local processing.

## 5. Next Steps
*   **Phase 5: Identity & Governance**: Now that we have a powerful "Robot" (Playwright), we must give it a secure ID card so we know *who* did what, and ensure it stays within its lane.
