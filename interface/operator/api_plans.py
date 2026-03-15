"""AG-19: Read-only plan/execution/verification API endpoints.

Endpoints:
  GET /api/plans              — list recent plans (last 50)
  GET /api/plans/latest       — most recent plan
  GET /api/executions         — list recent executions (last 50)
  GET /api/executions/latest  — most recent execution
  GET /api/verifications      — list recent verifications (last 50)
  GET /api/verifications/latest — most recent verification

All endpoints are READ-ONLY. No mutations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    _STARLETTE = True
except ImportError:
    _STARLETTE = False


def _state_root() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state"


def _read_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    bounded = max(1, min(int(limit), 200))
    return items[-bounded:]


def _read_latest(filename: str) -> dict[str, Any] | None:
    state = _state_root()
    if state is None:
        return None
    path = state / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Plan endpoints
# ---------------------------------------------------------------------------

async def plans_list(request: "Request") -> "JSONResponse":
    """GET /api/plans — list recent plans."""
    state = _state_root()
    if state is None:
        return JSONResponse({"error": "LUKA_RUNTIME_ROOT not set"}, status_code=503)
    items = _read_jsonl(state / "plan_log.jsonl")
    return JSONResponse({"plans": items, "count": len(items)})


async def plans_latest(request: "Request") -> "JSONResponse":
    """GET /api/plans/latest — most recent plan."""
    record = _read_latest("plan_latest.json")
    if record is None:
        return JSONResponse({"plan": None})
    return JSONResponse({"plan": record})


# ---------------------------------------------------------------------------
# Execution endpoints
# ---------------------------------------------------------------------------

async def executions_list(request: "Request") -> "JSONResponse":
    """GET /api/executions — list recent executions."""
    state = _state_root()
    if state is None:
        return JSONResponse({"error": "LUKA_RUNTIME_ROOT not set"}, status_code=503)
    items = _read_jsonl(state / "execution_log.jsonl")
    return JSONResponse({"executions": items, "count": len(items)})


async def executions_latest(request: "Request") -> "JSONResponse":
    """GET /api/executions/latest — most recent execution."""
    record = _read_latest("execution_latest.json")
    if record is None:
        return JSONResponse({"execution": None})
    return JSONResponse({"execution": record})


# ---------------------------------------------------------------------------
# Verification endpoints
# ---------------------------------------------------------------------------

async def verifications_list(request: "Request") -> "JSONResponse":
    """GET /api/verifications — list recent verifications."""
    state = _state_root()
    if state is None:
        return JSONResponse({"error": "LUKA_RUNTIME_ROOT not set"}, status_code=503)
    items = _read_jsonl(state / "verification_log.jsonl")
    return JSONResponse({"verifications": items, "count": len(items)})


async def verifications_latest(request: "Request") -> "JSONResponse":
    """GET /api/verifications/latest — most recent verification."""
    record = _read_latest("verification_latest.json")
    if record is None:
        return JSONResponse({"verification": None})
    return JSONResponse({"verification": record})


# ---------------------------------------------------------------------------
# Route list (for embedding in mission_control_server.py)
# ---------------------------------------------------------------------------

if _STARLETTE:
    routes = [
        Route("/api/plans", plans_list, methods=["GET"]),
        Route("/api/plans/latest", plans_latest, methods=["GET"]),
        Route("/api/executions", executions_list, methods=["GET"]),
        Route("/api/executions/latest", executions_latest, methods=["GET"]),
        Route("/api/verifications", verifications_list, methods=["GET"]),
        Route("/api/verifications/latest", verifications_latest, methods=["GET"]),
    ]
else:
    routes = []
