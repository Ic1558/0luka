"""AG-35: Repair Verification & Governance Reconciliation API handlers.

Read endpoints (no operator_id required):
  GET  /api/repair_reconciliation/history                — all reconciliation records
  GET  /api/repair_reconciliation/latest                 — latest reconciliation summary
  GET  /api/repair_reconciliation/{reconciliation_id}    — single reconciliation record

Write endpoints (operator_id required, 403 without):
  POST /api/repair_reconciliation/run                    — run reconciliation for an execution

AG-35 invariant: produces governance recommendations only.
                 Does NOT mutate drift_finding_status.json.
                 Does NOT close findings.
                 operator_action_required = True always.
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

async def repair_reconciliation_history() -> dict[str, Any]:
    """GET /api/repair_reconciliation/history — all reconciliation records."""
    try:
        from core.audit.reconciliation_store import list_reconciliation_records
        records = list_reconciliation_records()
        return {"ok": True, "records": records, "total": len(records)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_reconciliation_latest() -> dict[str, Any]:
    """GET /api/repair_reconciliation/latest — latest reconciliation summary."""
    try:
        from core.audit.reconciliation_store import load_reconciliation_latest
        summary = load_reconciliation_latest()
        return {"ok": True, "latest": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def repair_reconciliation_by_id(reconciliation_id: str) -> dict[str, Any]:
    """GET /api/repair_reconciliation/{reconciliation_id} — single reconciliation record."""
    try:
        from core.audit.reconciliation_store import get_reconciliation_record
        record = get_reconciliation_record(reconciliation_id)
        if record is None:
            return {"ok": False, "error": f"reconciliation_id {reconciliation_id!r} not found"}
        return {"ok": True, "reconciliation_id": reconciliation_id, "record": record}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def repair_reconciliation_run(request: "Request") -> "JSONResponse":
    """POST /api/repair_reconciliation/run — run reconciliation for an execution.

    Body: { "execution_id": "<id>", "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Produces governance recommendation only.
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

    execution_id = str(body.get("execution_id") or "").strip()
    if not execution_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "execution_id required"})

    try:
        from core.audit.repair_reconciliation import run_reconciliation
        result = run_reconciliation(execution_id, operator_id)
        status_code = 200 if result.get("ok") else 404
        return JSONResponse(status_code=status_code, content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"reconciliation failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_repair_reconciliation_routes(app: Any) -> None:
    """Register AG-35 routes on a FastAPI app instance."""
    app.add_api_route("/api/repair_reconciliation/history",                 repair_reconciliation_history,    methods=["GET"])
    app.add_api_route("/api/repair_reconciliation/latest",                  repair_reconciliation_latest,     methods=["GET"])
    app.add_api_route("/api/repair_reconciliation/{reconciliation_id}",     repair_reconciliation_by_id,      methods=["GET"])
    app.add_api_route("/api/repair_reconciliation/run",                     repair_reconciliation_run,        methods=["POST"])
