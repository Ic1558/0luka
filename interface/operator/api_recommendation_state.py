"""AG-61: Recommendation State Machine API."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


def _state_dir():
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")) / "state"

def _load(f):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def state_latest(request: Request) -> JSONResponse:
    d = _load("runtime_recommendation_state_latest.json")
    return JSONResponse(d or {})

async def state_index(request: Request) -> JSONResponse:
    return JSONResponse({"states": _load("runtime_recommendation_state_index.json") or []})

async def state_by_id(request: Request) -> JSONResponse:
    rec_id = request.path_params.get("recommendation_id", "")
    from runtime.recommendation_state_machine import get_state
    s = get_state(rec_id)
    return JSONResponse(s) if s else JSONResponse({"ok": False, "error": "not found"}, status_code=404)


def register_recommendation_state_routes(app: Any) -> None:
    app.add_api_route("/api/recommendation_state/latest", state_latest, methods=["GET"])
    app.add_api_route("/api/recommendation_state/index", state_index, methods=["GET"])
    app.add_api_route("/api/recommendation_state/{recommendation_id}", state_by_id, methods=["GET"])
