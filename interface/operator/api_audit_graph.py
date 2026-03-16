"""AG-64: Audit Graph API."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass


def _state_dir() -> Path:
    return Path(os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")) / "state"

def _load(f: str):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def graph_latest(request: Request) -> JSONResponse:
    d = _load("runtime_audit_graph_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def graph_index(request: Request) -> JSONResponse:
    return JSONResponse({"graphs": _load("runtime_audit_graph_index.json") or []})

async def graph_by_trace(request: Request) -> JSONResponse:
    trace_id = request.path_params.get("trace_id", "")
    from runtime.audit_graph import get_graph, build_graph
    g = get_graph(trace_id) or build_graph(trace_id)
    return JSONResponse(g)


def register_audit_graph_routes(app: Any) -> None:
    app.add_api_route("/api/audit_graph/latest", graph_latest, methods=["GET"])
    app.add_api_route("/api/audit_graph/index", graph_index, methods=["GET"])
    app.add_api_route("/api/audit_graph/{trace_id}", graph_by_trace, methods=["GET"])
