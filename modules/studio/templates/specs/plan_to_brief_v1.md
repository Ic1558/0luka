---
template_name: plan_to_interior_brief
type: opal_template
target_engine: studio_v1
inputs:
  - plan_pdf (hard_logic)
  - material_reference (image)
  - user_vibe (nlp)
---

# Opal Template Spec: Plan-to-Interior Brief (V1)

## Logic Flow (Local Forge)
1. **Extraction (Antigravity):** Extract spatial layout from `plan_pdf`. Identify room names, dimensions, and wall locations.
2. **Distillation (Gemini Flash):** Combine extracted layout with `material_reference` and `user_vibe`.
3. **Synthesis (Google Banana):** Generate a "Perfect Brief" (S2 Artifact) that maps room-by-room materials.

## One-Shot Requirements
- Create a Python handler `engines/plan_distiller.py` that parses the Plan JSON.
- Create a Prompt Template `prompts/studio/interior_alchemy.yaml`.
- Output: A valid S2 Intelligent Brief schema.

## Governance
- Must audit against `plan_pdf` for structural truth.
- Must achieve >80% alignment before passing to Render Lane.
