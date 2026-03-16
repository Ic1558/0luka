"""AG-69: Headless Runtime Supervisor API."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


async def supervisor_latest(request: Request) -> JSONResponse:
    from runtime.headless_supervisor import get_supervisor_latest
    d = get_supervisor_latest()
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)


async def supervisor_index(request: Request) -> JSONResponse:
    from runtime.headless_supervisor import list_supervisor_checks
    return JSONResponse({"checks": list_supervisor_checks()})


async def supervisor_check(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = body.get("operator_id", "system")
    try:
        from runtime.headless_supervisor import run_supervisor_check
        report = run_supervisor_check(operator_id=operator_id)
        return JSONResponse({"ok": True, "check_id": report["check_id"], "report": report})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_headless_supervisor_routes(app: Any) -> None:
    app.add_api_route("/api/headless_supervisor/latest", supervisor_latest, methods=["GET"])
    app.add_api_route("/api/headless_supervisor/index", supervisor_index, methods=["GET"])
    app.add_api_route("/api/headless_supervisor/check", supervisor_check, methods=["POST"])
