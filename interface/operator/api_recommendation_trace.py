"""AG-59: Recommendation Lifecycle Trace API."""
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
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")
    return Path(rt) / "state"

def _load(f):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def trace_latest(request: Request) -> JSONResponse:
    d = _load("runtime_recommendation_trace_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def trace_index(request: Request) -> JSONResponse:
    return JSONResponse({"traces": _load("runtime_recommendation_trace_index.json") or []})

async def trace_by_id(request: Request) -> JSONResponse:
    trace_id = request.path_params.get("trace_id", "")
    from runtime.recommendation_trace import get_trace
    t = get_trace(trace_id)
    return JSONResponse(t) if t else JSONResponse({"ok": False, "error": "not found"}, status_code=404)


def register_recommendation_trace_routes(app: Any) -> None:
    app.add_api_route("/api/recommendation_trace/latest", trace_latest, methods=["GET"])
    app.add_api_route("/api/recommendation_trace/index", trace_index, methods=["GET"])
    app.add_api_route("/api/recommendation_trace/{trace_id}", trace_by_id, methods=["GET"])
