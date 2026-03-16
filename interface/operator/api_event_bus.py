"""AG-63: Event Bus Normalization API."""
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
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    return Path(rt) / "state"

def _load(f: str):
    p = _state_dir() / f
    return json.loads(p.read_text()) if p.exists() else None


async def event_bus_latest(request: Request) -> JSONResponse:
    d = _load("runtime_event_bus_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def event_bus_index(request: Request) -> JSONResponse:
    return JSONResponse({"events": _load("runtime_event_bus_index.json") or []})

async def event_by_id(request: Request) -> JSONResponse:
    event_id = request.path_params.get("event_id", "")
    from runtime.event_bus_normalization import get_event
    e = get_event(event_id)
    return JSONResponse(e) if e else JSONResponse({"ok": False, "error": "not found"}, status_code=404)


def register_event_bus_routes(app: Any) -> None:
    app.add_api_route("/api/event_bus/latest", event_bus_latest, methods=["GET"])
    app.add_api_route("/api/event_bus/index", event_bus_index, methods=["GET"])
    app.add_api_route("/api/event_bus/{event_id}", event_by_id, methods=["GET"])
