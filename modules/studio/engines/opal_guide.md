# Opal Automation Recipe (v1)

This recipe is used by Antigravity to perform "Self-Editing" and "Self-Testing" on Opal projects.

## UI Selectors (Heuristic)

| Component | Selector / Method | Description |
| :--- | :--- | :--- |
| **Project URL** | `https://opal.google/edit/<id>` | The main editor link. |
| **Edit Box** | `textarea[placeholder="Edit these steps"]` | The primary agent prompt input. |
| **Send Button** | `button[aria-label="Send message"]` or Enter | Submits the edit prompt. |
| **Start Button** | `button:has-text("Start")` | Located in the right preview pane. |
| **Node Canvas** | `.canvas-container` | The visual logic area. |

## Automation Flow

1. **Navigate**: Open the provided Opal project URL.
2. **Sign-in**: Complete Google Sign-in if prompted (Handle 'Continue' button).
3. **Analyze**: Capture a screenshot of the existing node structure.
4. **Edit**: 
   - Type the user's natural language goal into the **Edit Box**.
   - Submit and wait for the "Applying changes..." overlay to disappear.
5. **Verify**:
   - Capture a post-edit screenshot of the canvas.
   - Click the **Start** button to run the mini-app.
   - Record the visual output (screenshot/bundle).
6. **Artifact**: Save all screenshots to `modules/studio/outputs/art_<ts>/`.
