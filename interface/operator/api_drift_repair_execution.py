"""AG-34: Supervised Drift Repair Execution API handlers.

Read endpoints (no operator_id required):
  GET  /api/drift_repair_execution/history          — all execution records
  GET  /api/drift_repair_execution/latest           — latest execution summary
  GET  /api/drift_repair_execution/{execution_id}   — single execution record

Write endpoints (operator_id required, 403 without):
  POST /api/drift_repair_execution/run              — run supervised repair execution
  POST /api/drift_repair_execution/verify           — re-run verification for an execution

AG-34 invariant: POST /run executes only APPROVED plans within approved scope.
                 Does NOT close findings. Does NOT modify baseline.
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def drift_repair_execution_history() -> dict[str, Any]:
    """GET /api/drift_repair_execution/history — all execution records."""
    try:
        from core.audit.repair_execution_store import list_execution_records
        records = list_execution_records()
        return {"ok": True, "records": records, "total": len(records)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_repair_execution_latest() -> dict[str, Any]:
    """GET /api/drift_repair_execution/latest — latest execution summary."""
    try:
        from core.audit.repair_execution_store import load_repair_execution_latest
        summary = load_repair_execution_latest()
        return {"ok": True, "latest": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_repair_execution_by_id(execution_id: str) -> dict[str, Any]:
    """GET /api/drift_repair_execution/{execution_id} — single execution record."""
    try:
        from core.audit.repair_execution_store import get_execution_record
        record = get_execution_record(execution_id)
        if record is None:
            return {"ok": False, "error": f"execution_id {execution_id!r} not found"}
        return {"ok": True, "execution_id": execution_id, "record": record}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

async def drift_repair_execution_run(request: "Request") -> "JSONResponse":
    """POST /api/drift_repair_execution/run — run supervised repair execution.

    Body: { "plan_id": "<id>", "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Executes only APPROVED plans within approved scope.
    Does NOT close findings. Does NOT modify baseline.
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

    plan_id = str(body.get("plan_id") or "").strip()
    if not plan_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "plan_id required"})

    try:
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        result = run_supervised_repair_execution(plan_id, operator_id)
        status_code = 200 if result.get("ok") else 422
        return JSONResponse(status_code=status_code, content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"execution failed: {exc}"},
        )


async def drift_repair_execution_verify(request: "Request") -> "JSONResponse":
    """POST /api/drift_repair_execution/verify — re-run verification for an execution.

    Body: { "execution_id": "<id>", "operator_id": "<id>" }

    Loads the execution record and re-runs the verification step.
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

    execution_id = str(body.get("execution_id") or "").strip()
    if not execution_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "execution_id required"})

    try:
        from core.audit.repair_execution_store import get_execution_record
        from core.audit.drift_repair_executor import (
            run_post_repair_verification,
            _load_plan_by_id,
        )
        record = get_execution_record(execution_id)
        if record is None:
            return JSONResponse(status_code=404, content={"ok": False, "reason": f"execution_id {execution_id!r} not found"})

        plan = _load_plan_by_id(record.get("plan_id", ""))
        if plan is None:
            return JSONResponse(status_code=404, content={"ok": False, "reason": "plan not found for re-verification"})

        pre_state = {"snapshots": record.get("before_state", [])}
        post_state = {"snapshots": record.get("after_state", [])}
        execution_data = {"executed_actions": record.get("executed_actions", [])}

        verification = run_post_repair_verification(plan, execution_data, pre_state, post_state)
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "execution_id": execution_id,
                "verification_status": verification.get("verification_status"),
                "checks": verification.get("checks", []),
                "triggered_by": operator_id,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"verification failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_drift_repair_execution_routes(app: Any) -> None:
    """Register AG-34 routes on a FastAPI app instance."""
    app.add_api_route("/api/drift_repair_execution/history",            drift_repair_execution_history,    methods=["GET"])
    app.add_api_route("/api/drift_repair_execution/latest",             drift_repair_execution_latest,     methods=["GET"])
    app.add_api_route("/api/drift_repair_execution/{execution_id}",     drift_repair_execution_by_id,      methods=["GET"])
    app.add_api_route("/api/drift_repair_execution/run",                drift_repair_execution_run,        methods=["POST"])
    app.add_api_route("/api/drift_repair_execution/verify",             drift_repair_execution_verify,     methods=["POST"])
