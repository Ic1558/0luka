# Implementation Plan: Structural Lock Audit & 3-Storey Protocol

This plan outlines the verification process for the "Structural Lock" mechanism and the expansion into 3-Storey vertical integrity.

## Objective
To ensure that architectural visualizations precisely adhere to the input geometry and vertical core logic (stairs, shafts) in multi-storey projects.

## Phase 1: Structural Lock Audit (COMPLETED)
- Verified Distiller -> Connector -> Opal Job chain for single sketch.
- Confirmed technical parameters (`control_weight`, `denoising_strength`) correctly locks pixels.

## Phase 2: 3-Storey Vertical Lock (NEW)
Implementing the "3-Storey Addendum" governance rules.

### 1. Engine Upgrade (Distiller)
- **File**: `modules/studio/engines/universal_studio_distiller.py`
- **Change**: Add `building.levels` support and "3rd Storey Architect" archetype.
- **Logic**: Enforce "Stacking Integrity" in the distilled prompt.

### 2. Connector Upgrade (AEC Lock)
- **File**: `modules/studio/connectors/opal_aec_connector.py`
- **Change**: Implement Dual-Level Locks.
    - **Level A (Strict)**: Weight 1.8+ for stairs/shafts.
    - **Level B (Guided)**: Managed denoising for furniture/materials.
- **Validation**: Add `Vera_Lite+` check for page-level mapping.

### 3. Execution on Boss's PDF
- **Source**: `/Users/icmini/My Drive (ittipong.c@gmail.com)/01_edge_works/Wei/1215/wsk49-251216_03.pdf`
- **Output**: 3-Storey Opal Job with explicit level mapping.

## Verification Plan
1. Run Distiller with `levels=3`.
2. Verify generated Job contains `Level A` and `Level B` parameters.
3. Confirm `stacking_report` requirement is in the system audit payload.
