"""AG-33: Drift Repair Planning API handlers.

Read endpoints (no operator_id required):
  GET  /api/drift_repair/plans                — all stored repair plans
  GET  /api/drift_repair/plans/{finding_id}   — plans for a specific finding

Write endpoint (operator_id required, 403 without):
  POST /api/drift_repair/run                  — trigger repair planning run

AG-33 invariant: POST /run only generates plans. It does NOT execute repair,
modify finding status, or change any codebase or baseline file.
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


async def drift_repair_plans_list() -> dict[str, Any]:
    """GET /api/drift_repair/plans — all stored repair plans."""
    try:
        from core.audit.drift_repair_planner import list_all_plans
        plans = list_all_plans()
        return {"ok": True, "plans": plans, "total": len(plans)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_repair_plan_by_finding(finding_id: str) -> dict[str, Any]:
    """GET /api/drift_repair/plans/{finding_id} — plans for a specific finding."""
    try:
        from core.audit.drift_repair_planner import get_plans_for_finding
        plans = get_plans_for_finding(finding_id)
        return {"ok": True, "finding_id": finding_id, "plans": plans, "total": len(plans)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_repair_run_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/drift_repair/run — trigger a repair planning run.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Reads ESCALATED findings, generates plans, stores them.
    Does NOT execute repair. Does NOT change finding status.
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
        from core.audit.drift_repair_planner import run_repair_planning
        summary = run_repair_planning()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "plans_generated": summary.get("plans_generated", 0),
                "escalated_found": summary.get("escalated_found", 0),
                "plans": summary.get("plans", []),
                "errors": summary.get("errors", []),
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"planning failed: {exc}"},
        )


def register_drift_repair_routes(app: Any) -> None:
    """Register AG-33 routes on a FastAPI app instance."""
    app.add_api_route("/api/drift_repair/plans",                drift_repair_plans_list,         methods=["GET"])
    app.add_api_route("/api/drift_repair/plans/{finding_id}",   drift_repair_plan_by_finding,    methods=["GET"])
    app.add_api_route("/api/drift_repair/run",                  drift_repair_run_endpoint,       methods=["POST"])
