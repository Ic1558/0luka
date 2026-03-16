"""AG-65: Runtime Replay API."""
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


async def replay_run(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)
    trace_id = body.get("trace_id", "")
    operator_id = body.get("operator_id", "unknown")
    if not trace_id:
        return JSONResponse({"ok": False, "error": "trace_id required"}, status_code=400)
    try:
        from runtime.runtime_replay import replay
        return JSONResponse(replay(trace_id, operator_id))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

async def replay_latest(request: Request) -> JSONResponse:
    d = _load("runtime_replay_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def replay_index(request: Request) -> JSONResponse:
    return JSONResponse({"replays": _load("runtime_replay_index.json") or []})


def register_runtime_replay_routes(app: Any) -> None:
    app.add_api_route("/api/runtime_replay/run", replay_run, methods=["POST"])
    app.add_api_route("/api/runtime_replay/latest", replay_latest, methods=["GET"])
    app.add_api_route("/api/runtime_replay/index", replay_index, methods=["GET"])
