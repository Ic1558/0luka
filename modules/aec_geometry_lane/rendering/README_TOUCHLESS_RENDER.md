# Touchless Rendering Setup (AEC Geometry Lane)

This guide documents the "Human-Touchless" rendering pipeline setup for SketchUp, allowing one-click automation from massing generation to material application.

## 🎯 Architecture

1.  **Massing Generation**: Python script generates `massing_v1.obj` and `render_params.yaml`.
2.  **Drive Sync**: Files are synced to Google Drive `_AI_INBOX`.
3.  **Automation Bot**: AppleScript (`render_bot.scpt`) controls SketchUp.
4.  **Logic Core**: Ruby Script (`apply_params.rb`) loads geometry and applies styles.

## 🛠 Prerequisites

1.  **macOS**: This automation relies on AppleScript.
2.  **SketchUp Pro**: Valid license and installed.
3.  **Permissions**:
    *   System Settings > Privacy & Security > Accessibility
    *   Allow **Script Editor** (or your terminal/Shortcuts app).
    *   Allow **SketchUp**.

## 🚀 Usage (One-Click)

1.  **Open SketchUp**.
2.  **Run the Bot**:
    *   Terminal: `osascript modules/aec_geometry_lane/rendering/runtime/render_bot.scpt`
    *   *Or* Double-click `render_bot.scpt` and press Run.
3.  **Watch Magic**:
    *   Script opens Ruby Console.
    *   Imports `massing_v1.obj` (ignoring default figures like Steve).
    *   Applies materials defined in `render_params.yaml`.
    *   Sets the camera scene (if defined).
    *   Shows a "✅ Style Applied" popup.

## 📂 File Structure

*   **Controller**: `modules/aec_geometry_lane/rendering/runtime/render_bot.scpt`
*   **Logic (Ruby)**: `drive/_AI_INBOX/apply_params.rb` (The script loaded by SketchUp)
*   **Data**:
    *   `massing_v1.obj` (The geometry)
    *   `render_params.yaml` (The AI style definition)

## 🔧 Troubleshooting

*   **"No active model found"**: Open a SketchUp file first (even a blank one).
*   **"Script didn't type anything"**: Ensure Accessibility permissions are enabled. The script needs to control keyboard input.
*   **"Nothing appeared"**: The script auto-imports only if it doesn't find "Wall/Floor" geometry. Try deleting everything (including Steve) and running again.
*   **Scene Error**: If camera doesn't move, check if `scene` key exists in YAML. If missing, it safely skips.

---
**Status**: Production Ready (Phase 3.1 Completed)
