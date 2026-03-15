"""AG-22/AG-23: Policy promotion + lifecycle API handlers.

Endpoints registered in mission_control_server.py:
  GET  /api/policies                    — list all policies (optionally filtered by status)
  GET  /api/policy_activation_log       — list activation log entries
  POST /api/promote_policy              — operator-triggered promotion (AG-22)
  POST /api/revoke_policy               — operator-triggered hard revoke (AG-23)
  POST /api/deprecate_policy            — operator-triggered soft deprecation (AG-23)
  POST /api/supersede_policy            — operator-triggered supersession (AG-23)

POST bodies all accept:
  { "policy_id": "<id>", "operator_id": "<operator>", ... }
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


def _load_candidate(candidate_id: str) -> dict[str, Any] | None:
    """Fetch a policy candidate from the AG-21 learning store."""
    try:
        from learning.policy_candidates import list_candidates
        for c in list_candidates(limit=500):
            if c.get("candidate_id") == candidate_id:
                return c
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# GET handlers
# ---------------------------------------------------------------------------

async def policies_list(status: str = "") -> dict[str, Any]:
    """GET /api/policies — return policies, optionally filtered by status.

    Query param: ?status=ACTIVE|DEPRECATED|REVOKED|SUPERSEDED|EXPIRED
    Default: all policies.
    """
    try:
        if status:
            from core.policy.policy_lifecycle import list_policies_by_status
            return {"policies": list_policies_by_status(status)}
        from core.policy.policy_registry import list_policies
        return {"policies": list_policies()}
    except Exception as exc:
        return {"policies": [], "error": str(exc)}


async def policy_activation_log() -> dict[str, Any]:
    """GET /api/policy_activation_log — return recent activation log."""
    try:
        from core.policy.policy_registry import list_activation_log
        return {"activation_log": list_activation_log(limit=100)}
    except Exception as exc:
        return {"activation_log": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# POST handler
# ---------------------------------------------------------------------------

async def promote_policy_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/promote_policy — operator-triggered policy promotion.

    Operator-only: rejects requests without a non-empty operator_id.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    candidate_id = str(body.get("candidate_id") or "").strip()
    if not candidate_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "candidate_id required"})

    # operator_id: prefer explicit body field; fall back to header X-Operator-Id
    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "reason": "operator_id required — promotion is operator-only"},
        )

    candidate = _load_candidate(candidate_id)
    if candidate is None:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "reason": f"candidate {candidate_id!r} not found"},
        )

    # Enforce operator approval state before reaching promoter
    if candidate.get("approval_state") != "APPROVED":
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "reason": f"candidate approval_state={candidate.get('approval_state')!r} — must be APPROVED",
            },
        )

    try:
        from core.policy.policy_promoter import promote
        result = promote(candidate, operator_id)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})

    status = 200 if result.get("ok") else 422
    return JSONResponse(status_code=status, content=result)


# ---------------------------------------------------------------------------
# AG-23 lifecycle POST handlers (operator-only)
# ---------------------------------------------------------------------------

async def revoke_policy_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/revoke_policy — operator-triggered hard revoke."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    policy_id, operator_id, err = _extract_policy_operator(body, request)
    if err:
        return err

    try:
        from core.policy.policy_lifecycle import revoke_policy
        result = revoke_policy(policy_id, operator_id, reason=str(body.get("reason") or ""))
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})

    return JSONResponse(status_code=200 if result["ok"] else 422, content=result)


async def deprecate_policy_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/deprecate_policy — operator-triggered soft deprecation."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    policy_id, operator_id, err = _extract_policy_operator(body, request)
    if err:
        return err

    try:
        from core.policy.policy_lifecycle import deprecate_policy
        result = deprecate_policy(policy_id, operator_id, reason=str(body.get("reason") or ""))
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})

    return JSONResponse(status_code=200 if result["ok"] else 422, content=result)


async def supersede_policy_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/supersede_policy — operator-triggered supersession."""
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    old_policy_id = str(body.get("policy_id") or "").strip()
    new_policy_id = str(body.get("new_policy_id") or "").strip()
    if not old_policy_id or not new_policy_id:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "reason": "policy_id and new_policy_id required"},
        )

    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "reason": "operator_id required"},
        )

    try:
        from core.policy.policy_lifecycle import supersede_policy
        result = supersede_policy(old_policy_id, new_policy_id, operator_id)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})

    return JSONResponse(status_code=200 if result["ok"] else 422, content=result)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _extract_policy_operator(
    body: dict[str, Any],
    request: "Request",
) -> "tuple[str, str, JSONResponse | None]":
    """Extract and validate policy_id + operator_id from request body/headers."""
    policy_id = str(body.get("policy_id") or "").strip()
    if not policy_id:
        return "", "", JSONResponse(
            status_code=400, content={"ok": False, "reason": "policy_id required"}
        )
    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()
    if not operator_id:
        return policy_id, "", JSONResponse(
            status_code=403,
            content={"ok": False, "reason": "operator_id required — lifecycle ops are operator-only"},
        )
    return policy_id, operator_id, None
