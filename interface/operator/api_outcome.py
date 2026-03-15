"""AG-30: Policy Outcome Governance API handlers.

Endpoints:
  GET  /api/policy_outcome_governance          — all governance records (latest per policy)
  GET  /api/policy_outcome_governance/{policy_id} — governance record for one policy
  GET  /api/policy_outcome_log                 — full append-only governance log
  POST /api/policy_outcome_action              — operator executes an action on a record
  POST /api/run_outcome_governance             — trigger evaluation + create governance record
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False


async def outcome_governance_list() -> dict[str, Any]:
    """GET /api/policy_outcome_governance — latest governance record per policy."""
    try:
        from core.policy.outcome_store import list_all_latest
        return {"governance": list_all_latest()}
    except Exception as exc:
        return {"governance": [], "error": str(exc)}


async def outcome_governance_log() -> dict[str, Any]:
    """GET /api/policy_outcome_log — recent governance log entries."""
    try:
        from core.policy.outcome_store import list_governance_log
        return {"log": list_governance_log(limit=100)}
    except Exception as exc:
        return {"log": [], "error": str(exc)}


async def outcome_action_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/policy_outcome_action — operator executes a governance action.

    Body:
      {
        "governance_id": "<id>",
        "action":        "RETAINED | ROLLED_BACK | QUARANTINED | SUPERSEDED | DISMISSED",
        "operator_id":   "<id>"
      }

    Side effects:
      - ROLLED_BACK  → calls revoke_policy()
      - QUARANTINED  → calls deprecate_policy()
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    governance_id = str(body.get("governance_id") or "").strip()
    action = str(body.get("action") or "").strip().upper()
    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()

    if not governance_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "governance_id required"})
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.policy.outcome_router import VALID_OPERATOR_ACTIONS
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"outcome_router unavailable: {exc}"})

    if action not in VALID_OPERATOR_ACTIONS:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "reason": f"invalid action {action!r}; valid: {sorted(VALID_OPERATOR_ACTIONS)}"},
        )

    try:
        import time
        from core.policy.outcome_store import update_governance_record, get_latest_for_policy
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Determine new status
        new_status = "DISMISSED" if action == "DISMISSED" else "ACTIONED"

        updated = update_governance_record(governance_id, {
            "status": new_status,
            "action_taken": action,
            "actioned_at": now,
            "actioned_by": operator_id,
        })
        if updated is None:
            return JSONResponse(status_code=404, content={"ok": False, "reason": f"governance_id {governance_id!r} not found"})

        # Side-effects: lifecycle calls for destructive actions
        policy_id = str(updated.get("policy_id") or "")
        side_effect_error: str | None = None

        if action == "ROLLED_BACK" and policy_id:
            try:
                from core.policy.policy_lifecycle import revoke_policy
                revoke_policy(policy_id, operator_id, reason=f"operator_rollback via governance_id={governance_id}")
            except Exception as exc:
                side_effect_error = f"revoke_policy failed: {exc}"

        elif action == "QUARANTINED" and policy_id:
            try:
                from core.policy.policy_lifecycle import deprecate_policy
                deprecate_policy(policy_id, operator_id, reason=f"operator_quarantine via governance_id={governance_id}")
            except Exception as exc:
                side_effect_error = f"deprecate_policy failed: {exc}"

        result: dict[str, Any] = {"ok": True, "record": updated}
        if side_effect_error:
            result["side_effect_warning"] = side_effect_error
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})


async def run_outcome_governance_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/run_outcome_governance — run effectiveness check + create governance record.

    Body: { "policy_id": "<id>", "operator_id": "<id>" }
    Operator-only.
    """
    if not _FASTAPI:
        return {"ok": False, "reason": "fastapi not available"}  # type: ignore[return-value]

    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "invalid JSON body"})

    policy_id = str(body.get("policy_id") or "").strip()
    operator_id = str(body.get("operator_id") or "").strip()
    if not operator_id:
        operator_id = str(request.headers.get("X-Operator-Id") or "").strip()

    if not policy_id:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "policy_id required"})
    if not operator_id:
        return JSONResponse(status_code=403, content={"ok": False, "reason": "operator_id required"})

    try:
        from core.policy.policy_effectiveness import run_and_persist
        from core.policy.outcome_router import route_verdict
        from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest

        effectiveness = run_and_persist(policy_id)
        recommendation = route_verdict(effectiveness)
        record = create_governance_record(recommendation)
        append_governance_record(record)
        write_latest(record)

        return JSONResponse(status_code=200, content={
            "ok": True,
            "effectiveness": effectiveness,
            "governance_record": record,
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": str(exc)})
