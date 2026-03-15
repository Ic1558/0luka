"""AG-29: Policy effectiveness API handlers.

Endpoints:
  GET  /api/policy_effectiveness              — all effectiveness records
  GET  /api/policy_effectiveness/{policy_id}  — single policy record
  GET  /api/policy_verification_log           — verification history
  POST /api/verify_policy_effectiveness       — run verification for a policy
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


async def effectiveness_list() -> dict[str, Any]:
    """GET /api/policy_effectiveness — all effectiveness records."""
    try:
        from core.policy.policy_effectiveness import list_effectiveness
        return {"effectiveness": list_effectiveness()}
    except Exception as exc:
        return {"effectiveness": [], "error": str(exc)}


async def effectiveness_verification_log() -> dict[str, Any]:
    """GET /api/policy_verification_log — recent verification log."""
    try:
        from core.policy.policy_effectiveness import list_verification_log
        return {"verification_log": list_verification_log(limit=100)}
    except Exception as exc:
        return {"verification_log": [], "error": str(exc)}


async def verify_policy_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/verify_policy_effectiveness — run effectiveness check.

    Body: { "policy_id": "<id>" }
    Operator-only: requires operator_id in body or X-Operator-Id header.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    policy_id = str(body.get("policy_id") or "").strip()
    if not policy_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "policy_id required"})

    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "reason": "operator_id required — verification is operator-only"},
        )

    try:
        from core.policy.policy_effectiveness import run_and_persist
        record = run_and_persist(policy_id)
        return JSONResponse(status_code=200, content={"ok": True, "record": record})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})
