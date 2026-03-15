"""AG-22: Policy promotion API handlers.

Endpoints registered in mission_control_server.py:
  GET  /api/policies               — list all promoted policies
  GET  /api/policy_activation_log  — list activation log entries
  POST /api/promote_policy         — operator-triggered promotion

POST /api/promote_policy contract:
  Request body (JSON):
    {
      "candidate_id": "<id>",
      "operator_id":  "<operator>"   # required; server may inject from session
    }
  Response (JSON):
    { "ok": true,  "policy_id": "<id>", "reason": "promoted"  }
    { "ok": false, "policy_id": null,   "reason": "<why>"     }
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

async def policies_list() -> dict[str, Any]:
    """GET /api/policies — return all promoted policies."""
    try:
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
