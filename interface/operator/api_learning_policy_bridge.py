"""AG-67: Learning-to-Policy Bridge API."""
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


async def bridge_latest(request: Request) -> JSONResponse:
    d = _load("runtime_learning_policy_bridge_latest.json")
    return JSONResponse(d) if d else JSONResponse({"ok": False, "error": "none"}, status_code=404)

async def bridge_index(request: Request) -> JSONResponse:
    return JSONResponse({"bridges": _load("runtime_learning_policy_bridge_index.json") or []})

async def bridge_run(request: Request) -> JSONResponse:
    try:
        from runtime.learning_policy_bridge import run_bridge
        records = run_bridge()
        return JSONResponse({"ok": True, "records": records, "count": len(records)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def register_learning_policy_bridge_routes(app: Any) -> None:
    app.add_api_route("/api/learning_policy_bridge/latest", bridge_latest, methods=["GET"])
    app.add_api_route("/api/learning_policy_bridge/index", bridge_index, methods=["GET"])
    app.add_api_route("/api/learning_policy_bridge/run", bridge_run, methods=["POST"])
