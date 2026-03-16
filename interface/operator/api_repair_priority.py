"""AG-38: Repair Priority Orchestration API handlers.

Read endpoints (no operator_id required):
  GET  /api/repair_priority/queue              — current priority queue
  GET  /api/repair_priority/latest             — latest run summary
  GET  /api/repair_priority/{finding_id}       — priority record for one finding

Write endpoint (operator_id required, 403 without):
  POST /api/repair_priority/run                — trigger priority orchestration run

AG-38 invariant: ordering-only. No governance mutation, no repair execution,
                 no approval, no baseline mutation. operator_action_required always.
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


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def repair_priority_queue() -> dict[str, Any]:
    """GET /api/repair_priority/queue — current priority queue."""
    try:
        data = _load_json("repair_priority_queue.json")
        if data is None:
            return {"ok": True, "queue": [], "total": 0}
        return {"ok": True, "queue": data.get("queue", []), "total": data.get("total", 0)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_priority_latest() -> dict[str, Any]:
    """GET /api/repair_priority/latest — latest orchestration run summary."""
    try:
        data = _load_json("repair_priority_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_priority_by_finding(finding_id: str) -> dict[str, Any]:
    """GET /api/repair_priority/{finding_id} — priority record for one finding."""
    try:
        data = _load_json("repair_priority_queue.json")
        if data is None:
            return {"ok": False, "error": "priority queue not yet generated"}
        queue = data.get("queue", [])
        for item in queue:
            if item.get("finding_id") == finding_id:
                return {"ok": True, "finding_id": finding_id, "item": item}
        return {"ok": False, "error": f"finding_id {finding_id!r} not in current queue"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def repair_priority_run(request: "Request") -> "JSONResponse":
    """POST /api/repair_priority/run — trigger repair priority orchestration.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Ordering-only. No governance mutation. No repair execution.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        result = run_repair_priority_orchestration()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "items": result["total_items"],
                "p1_count": result["p1_count"],
                "p2_count": result["p2_count"],
                "top_priority": result["top_priority"],
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"orchestration failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_repair_priority_routes(app: Any) -> None:
    """Register AG-38 routes on a FastAPI app instance."""
    app.add_api_route("/api/repair_priority/queue",           repair_priority_queue,       methods=["GET"])
    app.add_api_route("/api/repair_priority/latest",          repair_priority_latest,      methods=["GET"])
    app.add_api_route("/api/repair_priority/{finding_id}",    repair_priority_by_finding,  methods=["GET"])
    app.add_api_route("/api/repair_priority/run",             repair_priority_run,         methods=["POST"])
