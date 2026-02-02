"""
Backward-Compatible Shim for NLP Control Plane
==============================================
Re-exports app from modules/nlp_control_plane/.

MUST run from repo root:
    cd /Users/icmini/0luka
    python -m uvicorn tools.web_bridge.main:app --port 8000

Or use the module directly (preferred):
    python -m uvicorn modules.nlp_control_plane.app.main:app --port 8000

DEPRECATED: This shim exists for backward compatibility only.
            New code should import from modules.nlp_control_plane directly.
"""

try:
    from modules.nlp_control_plane.app.main import app, create_app
except ImportError as e:
    raise ImportError(
        "\n"
        "═══════════════════════════════════════════════════════════════════\n"
        " IMPORT ERROR: Cannot import NLP Control Plane module.\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "\n"
        " This shim MUST be run from the 0luka repo root:\n"
        "\n"
        "   cd /Users/icmini/0luka\n"
        "   ./runtime/venv/bin/python -m uvicorn tools.web_bridge.main:app --port 8000\n"
        "\n"
        " Or use the module directly (PREFERRED):\n"
        "\n"
        "   cd /Users/icmini/0luka\n"
        "   ./runtime/venv/bin/python -m uvicorn modules.nlp_control_plane.app.main:app --port 8000\n"
        "\n"
        "═══════════════════════════════════════════════════════════════════\n"
    ) from e

__all__ = ["app", "create_app"]

# Entry point for running directly
if __name__ == "__main__":
    import uvicorn
    # Localhost only for security
    uvicorn.run(app, host="127.0.0.1", port=8000)
