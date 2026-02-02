---
name: thom-vision
description: "Advanced Visual Intelligence for AEC (FastVLM + ControlNet)"
version: 1.0.0
---

# Thom-Vision Skill

This skill equips Thom (Studio Agent) with "Eyes" to understand architectural visual data and "Hands" to guide generation.

## Capabilities

1.  **Semantic Plan Reading (FastVLM)**
    *   **Input**: Clean Plan Image (from S1).
    *   **Action**: Identify room zones, structure (columns/walls), and suggest circulation paths.
    *   **Output**: Semantic JSON/YAML description of the space.

2.  **Visual Mood Analysis (FastVLM)**
    *   **Input**: Reference Image / Moodboard.
    *   **Action**: Extract material palette, lighting conditions, and architectural style.
    *   **Output**: `scene_brief.yaml` fragment.

3.  **Visual Control (ControlNet)**
    *   **Input**: Line Art Plan + Prompt.
    *   **Action**: Constrain the diffusion generation to strictly follow the plan lines.
    *   **Output**: Accurate perspective renders.

## Implementation Guide (Connector)

Because these models are heavy, this skill acts as a **Connector** to either:
*   **Local Inference**: Running `MLX` (Apple Silicon optimized) versions of FastVLM.
*   **Hybrid Inference**: Sending heavily compressed visual tokens to a cloud service (e.g., Opal) if local resources are tight.

## Usage

```zsh
# Analyze a plan for room types
studio analyze plan projects/demo/plan_clean_001.png --mode semantics

# Extract mood from a reference
studio analyze mood projects/demo/ref_living_room.jpg

# Generate with ControlNet constraint
studio render interior --plan projects/demo/plan_clean_001.png --control canny
```
