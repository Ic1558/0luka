"""AG-68: Operator Workbench API."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    return Path(rt) / "state"


async def workbench_latest(request: Request) -> JSONResponse:
    from runtime.operator_workbench import get_workbench_latest
    d = get_workbench_latest()
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)


async def workbench_index(request: Request) -> JSONResponse:
    from runtime.operator_workbench import list_workbench_snapshots
    return JSONResponse({"snapshots": list_workbench_snapshots()})


async def workbench_build(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    operator_id = body.get("operator_id", "system")
    try:
        from runtime.operator_workbench import build_workbench
        snapshot = build_workbench(operator_id=operator_id)
        return JSONResponse({"ok": True, "workbench_id": snapshot["workbench_id"], "snapshot": snapshot})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_operator_workbench_routes(app: Any) -> None:
    app.add_api_route("/api/operator_workbench/latest", workbench_latest, methods=["GET"])
    app.add_api_route("/api/operator_workbench/index", workbench_index, methods=["GET"])
    app.add_api_route("/api/operator_workbench/build", workbench_build, methods=["POST"])
