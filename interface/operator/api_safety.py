"""AG-24: Read-only safety API endpoints + emergency stop controls.

GET endpoints (read-only):
  /api/safety/status          — overall safety summary
  /api/safety/emergency_stop  — emergency stop state
  /api/safety/topology_mode   — current topology mode
  /api/safety/process_conflicts — latest process scan
  /api/safety/violations      — recent protected zone violations

POST endpoints (controlled mutations — emergency stop only):
  /api/safety/emergency_stop/activate  — activate emergency stop
  /api/safety/emergency_stop/clear     — clear emergency stop
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


def _safe_import(module: str, func: str):
    try:
        import importlib
        m = importlib.import_module(module)
        return getattr(m, func)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /api/safety/status
# ---------------------------------------------------------------------------

async def safety_status(request: "Request") -> "JSONResponse":
    """Overall safety summary."""
    es_fn = _safe_import("core.safety.emergency_stop", "get_emergency_stop_state")
    topo_fn = _safe_import("core.safety.topology_transition_gate", "get_topology_mode")

    es_state = es_fn() if es_fn else {"active": False, "reason": None}
    topo_mode = topo_fn() if topo_fn else "UNKNOWN"

    return JSONResponse({
        "emergency_stop": es_state.get("active", False),
        "topology_mode": topo_mode,
        "runtime_root_set": bool(os.environ.get("LUKA_RUNTIME_ROOT", "").strip()),
    })


# ---------------------------------------------------------------------------
# GET /api/safety/emergency_stop
# ---------------------------------------------------------------------------

async def emergency_stop_status(request: "Request") -> "JSONResponse":
    fn = _safe_import("core.safety.emergency_stop", "get_emergency_stop_state")
    state = fn() if fn else {"error": "module_unavailable"}
    return JSONResponse({"emergency_stop": state})


# ---------------------------------------------------------------------------
# POST /api/safety/emergency_stop/activate
# ---------------------------------------------------------------------------

async def emergency_stop_activate(request: "Request") -> "JSONResponse":
    try:
        body = await request.json()
        reason = str(body.get("reason") or "operator_request")
    except Exception:
        reason = "operator_request"
    fn = _safe_import("core.safety.emergency_stop", "activate_emergency_stop")
    if fn:
        fn(reason)
        return JSONResponse({"activated": True, "reason": reason})
    return JSONResponse({"error": "emergency_stop module unavailable"}, status_code=503)


# ---------------------------------------------------------------------------
# POST /api/safety/emergency_stop/clear
# ---------------------------------------------------------------------------

async def emergency_stop_clear(request: "Request") -> "JSONResponse":
    try:
        body = await request.json()
        operator_id = str(body.get("operator_id") or "operator")
    except Exception:
        operator_id = "operator"
    fn = _safe_import("core.safety.emergency_stop", "clear_emergency_stop")
    if fn:
        fn(operator_id)
        return JSONResponse({"cleared": True, "cleared_by": operator_id})
    return JSONResponse({"error": "emergency_stop module unavailable"}, status_code=503)


# ---------------------------------------------------------------------------
# GET /api/safety/topology_mode
# ---------------------------------------------------------------------------

async def topology_mode_status(request: "Request") -> "JSONResponse":
    fn = _safe_import("core.safety.topology_transition_gate", "get_topology_mode")
    mode = fn() if fn else "UNKNOWN"
    log_fn = _safe_import("core.safety.topology_transition_gate", "_state_root")
    recent: list[dict[str, Any]] = []
    try:
        if log_fn:
            root = log_fn()
            if root:
                log = root / "topology_transition_log.jsonl"
                if log.exists():
                    lines = log.read_text(encoding="utf-8").splitlines()
                    for line in lines[-10:]:
                        line = line.strip()
                        if line:
                            try:
                                recent.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
    except Exception:
        pass
    return JSONResponse({"topology_mode": mode, "recent_transitions": recent})


# ---------------------------------------------------------------------------
# GET /api/safety/process_conflicts
# ---------------------------------------------------------------------------

async def process_conflicts(request: "Request") -> "JSONResponse":
    fn = _safe_import("core.safety.process_concurrency_guard", "get_conflict_summary")
    if fn:
        summary = fn()
        return JSONResponse({"process_conflict": summary})
    return JSONResponse({"error": "process_concurrency_guard unavailable"}, status_code=503)


# ---------------------------------------------------------------------------
# GET /api/safety/violations
# ---------------------------------------------------------------------------

async def protected_zone_violations(request: "Request") -> "JSONResponse":
    fn = _safe_import("core.safety.protected_zone_guard", "get_recent_violations")
    violations = fn() if fn else []
    return JSONResponse({"violations": violations, "count": len(violations)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if _STARLETTE:
    routes = [
        Route("/api/safety/status", safety_status, methods=["GET"]),
        Route("/api/safety/emergency_stop", emergency_stop_status, methods=["GET"]),
        Route("/api/safety/emergency_stop/activate", emergency_stop_activate, methods=["POST"]),
        Route("/api/safety/emergency_stop/clear", emergency_stop_clear, methods=["POST"]),
        Route("/api/safety/topology_mode", topology_mode_status, methods=["GET"]),
        Route("/api/safety/process_conflicts", process_conflicts, methods=["GET"]),
        Route("/api/safety/violations", protected_zone_violations, methods=["GET"]),
    ]
else:
    routes = []
