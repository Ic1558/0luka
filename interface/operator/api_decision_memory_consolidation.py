"""AG-62: Decision Memory Consolidation API."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


def _state_dir():
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime"))) / "state"

def _load(f):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def memory_latest(request: Request) -> JSONResponse:
    d = _load("runtime_decision_memory_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def memory_index(request: Request) -> JSONResponse:
    return JSONResponse({"memories": _load("runtime_decision_memory_index.json") or []})

async def memory_by_trace(request: Request) -> JSONResponse:
    trace_id = request.path_params.get("trace_id", "")
    from runtime.decision_memory_consolidation import get_memory
    m = get_memory(trace_id)
    return JSONResponse(m) if m else JSONResponse({"ok": False, "error": "not found"}, status_code=404)


def register_decision_memory_consolidation_routes(app: Any) -> None:
    app.add_api_route("/api/decision_memory/latest", memory_latest, methods=["GET"])
    app.add_api_route("/api/decision_memory/index", memory_index, methods=["GET"])
    app.add_api_route("/api/decision_memory/{trace_id}", memory_by_trace, methods=["GET"])
