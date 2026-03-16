"""AG-48: Runtime Claim Verifier API handlers.

Read endpoints (no operator_id required):
  GET  /api/claim_verifier/latest      — latest verification report
  GET  /api/claim_verifier/verdicts    — slim verdict summary
  GET  /api/claim_verifier/mismatches  — inconsistent/unsupported claims only
  GET  /api/claim_verifier/evidence    — evidence reference list

Write endpoint (operator_id required, 403 without):
  POST /api/claim_verifier/run         — trigger claim verification run

AG-48 invariant: verification-only. No governance mutation, no campaign
mutation, no repair execution, no baseline mutation, no automatic claim
correction.
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


def _load_json(filename: str, runtime_root: str | None = None) -> Any:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        return None
    path = Path(rt) / "state" / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

async def claim_verifier_latest() -> dict[str, Any]:
    """GET /api/claim_verifier/latest — latest claim verification report."""
    try:
        data = _load_json("runtime_claim_verification_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_verifier_verdicts() -> dict[str, Any]:
    """GET /api/claim_verifier/verdicts — slim verdict summary."""
    try:
        data = _load_json("runtime_claim_verdicts.json")
        if data is None:
            return {
                "ok": True, "verified_count": 0, "inconsistent_count": 0,
                "unsupported_count": 0, "total_claims": 0, "top_issue": None,
            }
        return {
            "ok":                True,
            "verified_count":    data.get("verified_count", 0),
            "inconsistent_count": data.get("inconsistent_count", 0),
            "unsupported_count": data.get("unsupported_count", 0),
            "total_claims":      data.get("total_claims", 0),
            "top_issue":         data.get("top_issue"),
            "verdicts":          data.get("verdicts", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_verifier_mismatches() -> dict[str, Any]:
    """GET /api/claim_verifier/mismatches — inconsistent/unsupported claims."""
    try:
        data = _load_json("runtime_claim_verification_latest.json")
        if data is None:
            return {"ok": True, "mismatches": [], "mismatch_count": 0}
        return {
            "ok":            True,
            "mismatches":    data.get("mismatches", []),
            "mismatch_count": len(data.get("mismatches", [])),
            "top_issue":     data.get("top_issue"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_verifier_evidence() -> dict[str, Any]:
    """GET /api/claim_verifier/evidence — evidence reference list."""
    try:
        data = _load_json("runtime_claim_verification_latest.json")
        if data is None:
            return {"ok": True, "evidence_refs": []}
        return {
            "ok":           True,
            "evidence_refs": data.get("evidence_refs", []),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Write endpoint
# ---------------------------------------------------------------------------

async def claim_verifier_run(request: "Request") -> "JSONResponse":
    """POST /api/claim_verifier/run — trigger claim verification run."""
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
        from runtime.claim_verifier import run_claim_verification
        result = run_claim_verification()
        return JSONResponse(status_code=200, content={
            "ok":                True,
            "triggered_by":      operator_id,
            "verified_claims":   result["verified_count"],
            "inconsistent_claims": result["inconsistent_count"],
            "top_issue":         result["top_issue"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"claim verification failed: {exc}"})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_claim_verifier_routes(app: Any) -> None:
    """Register AG-48 routes on a FastAPI app instance."""
    app.add_api_route("/api/claim_verifier/latest",     claim_verifier_latest,    methods=["GET"])
    app.add_api_route("/api/claim_verifier/verdicts",   claim_verifier_verdicts,  methods=["GET"])
    app.add_api_route("/api/claim_verifier/mismatches", claim_verifier_mismatches, methods=["GET"])
    app.add_api_route("/api/claim_verifier/evidence",   claim_verifier_evidence,  methods=["GET"])
    app.add_api_route("/api/claim_verifier/run",        claim_verifier_run,       methods=["POST"])
