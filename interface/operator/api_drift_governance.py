"""AG-32: Drift Governance API handlers.

Read endpoints (no operator_id required):
  GET  /api/drift_governance/status          — all governed finding statuses
  GET  /api/drift_governance/log             — governance action log
  GET  /api/drift_governance/open            — OPEN findings only
  GET  /api/drift_governance/proposals       — baseline promotion proposals

Write endpoints (operator_id required, 403 without):
  POST /api/drift_governance/accept
  POST /api/drift_governance/dismiss
  POST /api/drift_governance/escalate
  POST /api/drift_governance/resolve
  POST /api/drift_governance/promote_to_baseline

Request body for all write endpoints:
  { "finding_id": "<id>", "operator_id": "<id>", "note": "<optional>" }
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
# Helpers
# ---------------------------------------------------------------------------

def _extract_operator(body: dict[str, Any], request: "Request") -> str:
    """Extract operator_id from body or X-Operator-Id header."""
    op = str(body.get("operator_id") or "").strip()
    if not op:
        op = str(request.headers.get("X-Operator-Id") or "").strip()
    return op


async def _write_action(
    request: "Request",
    action_fn: Any,
    action_name: str,
) -> "JSONResponse":
    """Common path for all write endpoints."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    operator_id = _extract_operator(body, request)
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    finding_id = str(body.get("finding_id") or "").strip()
    if not finding_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "finding_id required"})

    note = str(body.get("note") or "").strip() or None

    try:
        result = action_fn(finding_id, operator_id, note)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "finding_id": finding_id, "action": action_name, "result": result},
        )
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "reason": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"governance error: {exc}"})


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def drift_governance_status() -> dict[str, Any]:
    """GET /api/drift_governance/status — all governed finding statuses."""
    try:
        from core.audit.drift_governance_store import list_finding_status
        return {"ok": True, "statuses": list_finding_status()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_governance_log() -> dict[str, Any]:
    """GET /api/drift_governance/log — governance action log (most recent 200)."""
    try:
        from core.audit.drift_governance_store import list_governance_log
        return {"ok": True, "log": list_governance_log(limit=200)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_governance_open() -> dict[str, Any]:
    """GET /api/drift_governance/open — OPEN findings only."""
    try:
        from core.audit.drift_governance import list_open_findings
        return {"ok": True, "open_findings": list_open_findings()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def drift_governance_proposals() -> dict[str, Any]:
    """GET /api/drift_governance/proposals — baseline promotion proposals."""
    try:
        from core.audit.drift_governance_store import list_baseline_proposals
        return {"ok": True, "proposals": list_baseline_proposals()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------

async def drift_governance_accept(request: "Request") -> "JSONResponse":
    """POST /api/drift_governance/accept — mark finding as ACCEPTED."""
    from core.audit.drift_governance import accept_finding
    return await _write_action(request, accept_finding, "ACCEPTED")


async def drift_governance_dismiss(request: "Request") -> "JSONResponse":
    """POST /api/drift_governance/dismiss — mark finding as DISMISSED."""
    from core.audit.drift_governance import dismiss_finding
    return await _write_action(request, dismiss_finding, "DISMISSED")


async def drift_governance_escalate(request: "Request") -> "JSONResponse":
    """POST /api/drift_governance/escalate — mark finding as ESCALATED."""
    from core.audit.drift_governance import escalate_finding
    return await _write_action(request, escalate_finding, "ESCALATED")


async def drift_governance_resolve(request: "Request") -> "JSONResponse":
    """POST /api/drift_governance/resolve — mark finding as RESOLVED."""
    from core.audit.drift_governance import resolve_finding
    return await _write_action(request, resolve_finding, "RESOLVED")


async def drift_governance_promote(request: "Request") -> "JSONResponse":
    """POST /api/drift_governance/promote_to_baseline — propose baseline promotion."""
    from core.audit.drift_governance import promote_to_baseline
    return await _write_action(request, promote_to_baseline, "PROMOTE_TO_BASELINE")


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_drift_governance_routes(app: Any) -> None:
    """Register AG-32 routes on a FastAPI app instance."""
    app.add_api_route("/api/drift_governance/status",            drift_governance_status,   methods=["GET"])
    app.add_api_route("/api/drift_governance/log",               drift_governance_log,      methods=["GET"])
    app.add_api_route("/api/drift_governance/open",              drift_governance_open,     methods=["GET"])
    app.add_api_route("/api/drift_governance/proposals",         drift_governance_proposals, methods=["GET"])
    app.add_api_route("/api/drift_governance/accept",            drift_governance_accept,   methods=["POST"])
    app.add_api_route("/api/drift_governance/dismiss",           drift_governance_dismiss,  methods=["POST"])
    app.add_api_route("/api/drift_governance/escalate",          drift_governance_escalate, methods=["POST"])
    app.add_api_route("/api/drift_governance/resolve",           drift_governance_resolve,  methods=["POST"])
    app.add_api_route("/api/drift_governance/promote_to_baseline", drift_governance_promote, methods=["POST"])
