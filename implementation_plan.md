# Implementation Plan: Structural Lock Audit

This plan outlines the verification process for the "Structural Lock" mechanism in the 0luka Studio pipeline.

## Objective
To ensure that architectural visualizations precisely adhere to the input geometry by leveraging technical parameters (ControlNet weights, denoising limits) distilled from local AI prompts.

## Proposed Changes
No core logic changes are expected, but we will execute the full chain to verify correctness.

### 1. Distillation Phase
- **Tool**: `modules/studio/engines/universal_studio_distiller.py`
- **Input**: `interface/opal_bridge/assets/pilot_sketch.png`
- **Task**: Distill the intent into a high-fidelity 'Perfect Prompt' and structured payload.

### 2. Connection (Lock) Phase
- **Tool**: `modules/studio/connectors/opal_aec_connector.py`
- **Task**: Convert the payload into an Opal Job with strict 'Structural Lock' parameters (`control_weight`, `denoising_strength`).

### 3. Verification Phase (Audit)
- Inspect the generated JSON job file.
- Validate parameters against the mode-specific requirements (e.g., Sketch: Weight 1.5, Denoising 0.45).
- Verify the Opal Bridge UI displays these values correctly.

## Verification Plan
1. Run Distiller command.
2. Run Connector command.
3. `cat` the output JSON.
4. Report on fidelity score and technical lock status.
