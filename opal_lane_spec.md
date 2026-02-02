# Opal Hybrid Lane Architecture (Phase 6)

## Purpose
To enable fully authorized, autonomous bridging between **Google Opal (Cloud)** and **0luka Studio (Local)**, bypassing manual GMX confirmation for trusted visual logic tasks.

## Components

### 1. Dedicated Module (`modules/opal`)
A separate lane from standard Studio to enforce distinct governance policies.
- **Path**: `modules/opal/`
- **Identity**: `author: opal_agent` (Trusted System Actor)
- **Scope**: Can read/write to `modules/studio/inbox` and `modules/studio/outputs`.

### 2. Authorized Browser Agent
A headless (or visible) automation wrapper that holds the Google Session credentials securely.
- **Role**: Executes the "Edit" and "Run" actions on Opal URLs.
- **Auth**: Reuses the user's active browser session (via 0luka's browser tools) but operates under a "System Delegate" flag.

### 3. Fast-Track Policy
Artifacts produced by the Opal Lane are pre-validated for Studio consumption.
- **Flow**: `Opal(Cloud)` -> `Opal Lane(Local)` -> `Studio Lane(Inbox)` -> `Production Artifact`
- **Gate**: No manual approval required for this specific pipeline.

## Implementation Steps
1. **Scaffold**: Create `modules/opal/` with `connector` and `agent` subdirs.
2. **Policy**: Define `allow_opal_fast_track` in governance.
3. **Bridge**: Script `opal_bridge.zsh` to poll for tasks and drive the browser automation.
