# SketchUp Slot Specification (Phase 3.1)
**Status:** PROPOSED
**Engine:** SketchUp Pro + Ruby Automation
**Philosophy:** Geometry is Law. Parameter is Decor.

## 1. Governance Rules
1.  **Strict Import:** `massing_v1.obj` must be imported in **Meters**.
2.  **Zero-Edit:** No manual or AI modification of faces/edges allowed.
3.  **Naming Convention:** Tags and Materials must strictly follow this contract.

## 2. Tag Structure (Layers)
Every group must be assigned to one of these tags:
- `TAG_WALL`: Vertical partitions.
- `TAG_FLOOR_SMALL`: Room flooring (e.g. wood).
- `TAG_FLOOR_LARGE`: Hallway/Common flooring (e.g. concrete).
- `TAG_CEILING`: Horizontal top planes.

## 3. Material Slots (API Contract)
The renderer (Enscape/Twinmotion/V-Ray) will look for these names.
The AI selects which *type* of material fills these slots.

| Slot Name (In SketchUp) | Allowed AI Values (Mapping) |
| :--- | :--- |
| `MAT_WALL_SLOT` | `lime_plaster`, `exposed_brick`, `concrete_raw` |
| `MAT_FLOOR_SMALL_SLOT` | `oak_wood`, `walnut_wood`, `white_tile` |
| `MAT_FLOOR_LARGE_SLOT` | `polished_concrete`, `grey_slate`, `terrazzo` |
| `MAT_CEILING_SLOT` | `gypsum_white`, `acoustic_panel`, `exposed_slab` |

## 4. Scene Slots (Cameras)
| Scene Name | Description | Locked Attributes |
| :--- | :--- | :--- |
| `SCENE_ISO_TOP` | Isometric Overview | Parallel Projection, Fit Bounds |
| `SCENE_INTERIOR_EYE` | Human Perspective | Eye Height 1.6m, FOV 60° |

## 5. Automation Interface
The AI Stylist generates `render_params.yaml`:
```yaml
style: japandi
scene: SCENE_INTERIOR_EYE
materials:
  TAG_WALL: lime_plaster
  TAG_FLOOR_SMALL: oak_wood
  TAG_FLOOR_LARGE: polished_concrete
```
The Ruby script applies these choices to the `MAT_*_SLOT` materials.
