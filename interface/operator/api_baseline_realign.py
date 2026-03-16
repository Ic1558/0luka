"""AG-36: Baseline Realignment & Structural Drift Prevention API handlers.

Read endpoints (no operator_id required):
  GET  /api/baseline_realign/proposals   — all baseline realignment proposals
  GET  /api/baseline_realign/latest      — latest realignment run summary
  GET  /api/baseline_realign/patterns    — detected structural drift patterns

Write endpoint (operator_id required, 403 without):
  POST /api/baseline_realign/run         — trigger baseline realignment run

AG-36 invariant: POST /run generates proposals and detects patterns only.
                 Never mutates audit_baseline.py or canonical architecture docs.
                 Never changes governance state. operator_action_required = True always.
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

async def baseline_realign_proposals() -> dict[str, Any]:
    """GET /api/baseline_realign/proposals — all baseline realignment proposals."""
    try:
        from core.audit.baseline_realigner import list_all_proposals
        proposals = list_all_proposals()
        return {"ok": True, "proposals": proposals, "total": len(proposals)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def baseline_realign_latest() -> dict[str, Any]:
    """GET /api/baseline_realign/latest — latest realignment run summary."""
    try:
        from core.audit.baseline_realigner import _state_dir
        import json, os
        from pathlib import Path
        rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
        if not rt:
            return {"ok": True, "latest": {}}
        path = Path(rt) / "state" / "baseline_realign_latest.json"
        if not path.exists():
            return {"ok": True, "latest": {}}
        return {"ok": True, "latest": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def baseline_realign_patterns() -> dict[str, Any]:
    """GET /api/baseline_realign/patterns — detected structural drift patterns."""
    try:
        from core.audit.structural_drift_guard import list_all_patterns
        patterns = list_all_patterns()
        return {"ok": True, "patterns": patterns, "total": len(patterns)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def baseline_realign_run(request: "Request") -> "JSONResponse":
    """POST /api/baseline_realign/run — trigger baseline realignment run.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Generates proposals from reconciled findings and detects recurring patterns.
    Does NOT mutate canonical docs or baseline. Does NOT change governance state.
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
        from core.audit.baseline_realigner import run_baseline_realignment
        from core.audit.structural_drift_guard import detect_and_store_patterns
        summary = run_baseline_realignment()
        patterns = detect_and_store_patterns()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "proposals_generated": summary.get("proposals_generated", 0),
                "findings_evaluated": summary.get("findings_evaluated", 0),
                "patterns_detected": len(patterns),
                "errors": summary.get("errors", []),
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"realignment failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_baseline_realign_routes(app: Any) -> None:
    """Register AG-36 routes on a FastAPI app instance."""
    app.add_api_route("/api/baseline_realign/proposals", baseline_realign_proposals, methods=["GET"])
    app.add_api_route("/api/baseline_realign/latest",    baseline_realign_latest,   methods=["GET"])
    app.add_api_route("/api/baseline_realign/patterns",  baseline_realign_patterns, methods=["GET"])
    app.add_api_route("/api/baseline_realign/run",       baseline_realign_run,      methods=["POST"])
