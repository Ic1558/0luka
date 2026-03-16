"""AG-72: Sovereign Operator Mode API."""
from __future__ import annotations
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


async def sovereign_latest(request: Request) -> JSONResponse:
    from runtime.sovereign_operator import get_sovereign_latest
    d = get_sovereign_latest()
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)


async def sovereign_index(request: Request) -> JSONResponse:
    from runtime.sovereign_operator import list_sovereign_sessions
    return JSONResponse({"sessions": list_sovereign_sessions()})


async def sovereign_enter(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = body.get("operator_id", "")
    if not operator_id:
        return JSONResponse({"ok": False, "error": "operator_id_required"}, status_code=400)
    try:
        from runtime.sovereign_operator import enter_sovereign_mode
        session = enter_sovereign_mode(operator_id=operator_id)
        return JSONResponse({"ok": True, "session_id": session["session_id"], "session": session})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_sovereign_operator_routes(app: Any) -> None:
    app.add_api_route("/api/sovereign_operator/latest", sovereign_latest, methods=["GET"])
    app.add_api_route("/api/sovereign_operator/index", sovereign_index, methods=["GET"])
    app.add_api_route("/api/sovereign_operator/enter", sovereign_enter, methods=["POST"])
