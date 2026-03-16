"""AG-39: Supervised Repair Wave Scheduler API handlers.

Read endpoints (no operator_id required):
  GET  /api/repair_wave/schedule               — current wave schedule
  GET  /api/repair_wave/latest                 — latest run summary
  GET  /api/repair_wave/{wave_id}              — one wave by ID

Write endpoints (operator_id required, 403 without):
  POST /api/repair_wave/run                    — trigger wave scheduling run
  POST /api/repair_wave/{wave_id}/approve      — approve a PROPOSED wave
  POST /api/repair_wave/{wave_id}/reject       — reject a PROPOSED wave

AG-39 invariant: scheduling-only. No governance mutation, no repair execution,
                 no approval of findings, no baseline mutation. operator_action_required always.
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


def _load_json(filename: str, runtime_root: str | None = None) -> Any:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        return None
    path = Path(rt) / "state" / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _operator_id_from(body: dict[str, Any], request: "Request") -> str:
    oid = str(body.get("operator_id") or "").strip()
    if not oid:
        oid = str(request.headers.get("X-Operator-Id") or "").strip()
    return oid


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def repair_wave_schedule() -> dict[str, Any]:
    """GET /api/repair_wave/schedule — current wave schedule."""
    try:
        data = _load_json("repair_wave_schedule.json")
        if data is None:
            return {"ok": True, "waves": [], "total_waves": 0, "deferred_items": 0}
        return {
            "ok": True,
            "waves": data.get("waves", []),
            "total_waves": data.get("total_waves", 0),
            "deferred_items": data.get("deferred_items", 0),
            "total_items": data.get("total_items", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_wave_latest() -> dict[str, Any]:
    """GET /api/repair_wave/latest — latest scheduling run summary."""
    try:
        data = _load_json("repair_wave_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_wave_by_id(wave_id: str) -> dict[str, Any]:
    """GET /api/repair_wave/{wave_id} — one wave by ID."""
    try:
        data = _load_json("repair_wave_schedule.json")
        if data is None:
            return {"ok": False, "error": "no wave schedule found"}
        for wave in data.get("waves", []):
            if wave.get("wave_id") == wave_id:
                return {"ok": True, "wave_id": wave_id, "wave": wave}
        return {"ok": False, "error": f"wave_id {wave_id!r} not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

async def repair_wave_run(request: "Request") -> "JSONResponse":
    """POST /api/repair_wave/run — trigger repair wave scheduling.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Scheduling-only. No governance mutation. No repair execution.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _operator_id_from(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        result = run_repair_wave_scheduling()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "total_waves": result["total_waves"],
                "total_items_scheduled": result["total_items_scheduled"],
                "deferred_items": result["deferred_items"],
                "p1_wave_count": result["p1_wave_count"],
                "stability_classification": result["stability_classification"],
                "first_wave_id": result["first_wave_id"],
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"wave scheduling failed: {exc}"},
        )


async def repair_wave_approve(wave_id: str, request: "Request") -> "JSONResponse":
    """POST /api/repair_wave/{wave_id}/approve — approve a PROPOSED wave.

    Body: { "operator_id": "<id>" }
    Transitions wave from PROPOSED → APPROVED.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _operator_id_from(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.audit.repair_wave_scheduler import approve_repair_wave
        result = approve_repair_wave(wave_id, operator_id)
        if result["ok"]:
            return JSONResponse(status_code=200, content=result)
        return JSONResponse(status_code=409, content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"approve failed: {exc}"},
        )


async def repair_wave_reject(wave_id: str, request: "Request") -> "JSONResponse":
    """POST /api/repair_wave/{wave_id}/reject — reject a PROPOSED wave.

    Body: { "operator_id": "<id>", "reason": "<optional reason>" }
    Transitions wave from PROPOSED → REJECTED.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _operator_id_from(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    reason = str(body.get("reason") or "").strip()

    try:
        from core.audit.repair_wave_scheduler import reject_repair_wave
        result = reject_repair_wave(wave_id, operator_id, reason)
        if result["ok"]:
            return JSONResponse(status_code=200, content=result)
        return JSONResponse(status_code=409, content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"reject failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_repair_wave_routes(app: Any) -> None:
    """Register AG-39 routes on a FastAPI app instance."""
    app.add_api_route("/api/repair_wave/schedule",              repair_wave_schedule,   methods=["GET"])
    app.add_api_route("/api/repair_wave/latest",                repair_wave_latest,     methods=["GET"])
    app.add_api_route("/api/repair_wave/{wave_id}",             repair_wave_by_id,      methods=["GET"])
    app.add_api_route("/api/repair_wave/run",                   repair_wave_run,        methods=["POST"])
    app.add_api_route("/api/repair_wave/{wave_id}/approve",     repair_wave_approve,    methods=["POST"])
    app.add_api_route("/api/repair_wave/{wave_id}/reject",      repair_wave_reject,     methods=["POST"])
