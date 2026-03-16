"""AG-58: Mission Control Chain Runner API handlers.

Endpoints:
  GET  /api/chains         — list available chain names
  GET  /api/chains/latest  — latest chain run report
  GET  /api/chains/index   — index of all chain runs
  POST /api/chains/run     — run a named chain
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


def _load_json(filename: str) -> Any:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        return None
    path = Path(rt) / "state" / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


async def chains_list() -> dict[str, Any]:
    """GET /api/chains — return available chain names."""
    try:
        from runtime.chain_runner_policy import CHAIN_REGISTRY
        return {"chains": list(CHAIN_REGISTRY.keys())}
    except Exception as exc:
        return {"chains": [], "error": str(exc)}


async def chains_latest() -> dict[str, Any]:
    """GET /api/chains/latest — latest chain run report."""
    try:
        data = _load_json("runtime_chain_runner_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def chains_index() -> dict[str, Any]:
    """GET /api/chains/index — index of all chain runs."""
    try:
        data = _load_json("runtime_chain_runner_index.json")
        return {"ok": True, "index": data or []}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def chains_run(request: "Request") -> "JSONResponse":
    """POST /api/chains/run — run a named chain."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    chain_name = str(body.get("chain_name") or "").strip()
    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})
    if not chain_name:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "chain_name required"})

    try:
        from runtime.chain_runner import run_chain
        report = run_chain(chain_name, operator_id)
        return JSONResponse(status_code=200, content={"ok": True, "report": report})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "reason": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


def register_chain_runner_routes(app: Any) -> None:
    """Register AG-58 routes on a FastAPI/Starlette app instance."""
    app.add_api_route("/api/chains",        chains_list,   methods=["GET"])
    app.add_api_route("/api/chains/latest", chains_latest, methods=["GET"])
    app.add_api_route("/api/chains/index",  chains_index,  methods=["GET"])
    app.add_api_route("/api/chains/run",    chains_run,    methods=["POST"])
