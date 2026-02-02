"""
NLP Control Plane Module
========================
Natural language interface for 0luka task submission.

SECURITY INVARIANTS:
- NO subprocess/exec/eval in gateway
- Writes limited to interface/inbox/, interface/pending_approval/
- All operations logged to observability/telemetry/gateway.jsonl
- Author always server-injected as "gmx"

Usage:
    # Direct (preferred)
    uvicorn modules.nlp_control_plane.app.main:app --port 8000

    # Via shim (backward compat, from repo root only)
    uvicorn tools.web_bridge.main:app --port 8000
"""
__version__ = "1.0.0"

# Lazy import to avoid circular deps
def get_app():
    """Get the FastAPI app instance."""
    from .app.main import app
    return app
