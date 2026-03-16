"""AG-31: Runtime Self-Audit API handlers.

Endpoints:
  GET  /api/self_audit/latest    — most recent audit result (runtime_self_audit.json)
  GET  /api/self_audit/findings  — recent drift findings (drift_findings.jsonl, last N)
  POST /api/self_audit/run       — trigger a fresh audit run (operator_id required)

AG-31 invariant: GET endpoints are read-only.
POST /run triggers the audit engine but never auto-repairs drift or modifies
policy state, registry, or governance records.
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


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    return Path(rt) / "state"


async def self_audit_latest() -> dict[str, Any]:
    """GET /api/self_audit/latest — return most recent audit result."""
    try:
        path = _state_dir() / "runtime_self_audit.json"
        if not path.exists():
            return {"ok": True, "audit": None, "message": "no audit run yet"}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"ok": True, "audit": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def self_audit_findings() -> dict[str, Any]:
    """GET /api/self_audit/findings — return recent drift findings (last 200)."""
    try:
        path = _state_dir() / "drift_findings.jsonl"
        if not path.exists():
            return {"ok": True, "findings": [], "message": "no audit run yet"}
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        findings = []
        for line in lines[-200:]:
            try:
                findings.append(json.loads(line))
            except Exception:
                pass
        return {"ok": True, "findings": findings, "total": len(lines)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def self_audit_run_endpoint(request: "Request") -> "JSONResponse":
    """POST /api/self_audit/run — trigger a fresh audit run.

    Body: { "operator_id": "<id>" }
    Header alternative: X-Operator-Id

    Returns the new audit result.
    Does NOT repair drift. Does NOT modify policy state or registry.
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
        from core.audit.runtime_self_audit import run_runtime_self_audit
        result = run_runtime_self_audit()
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "triggered_by": operator_id,
                "verdict": result.get("overall_verdict"),
                "audit": result,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "reason": f"audit failed: {exc}"},
        )


def register_self_audit_routes(app: Any) -> None:
    """Register AG-31 routes on a FastAPI app instance."""
    app.add_api_route("/api/self_audit/latest",   self_audit_latest,          methods=["GET"])
    app.add_api_route("/api/self_audit/findings",  self_audit_findings,        methods=["GET"])
    app.add_api_route("/api/self_audit/run",       self_audit_run_endpoint,    methods=["POST"])
