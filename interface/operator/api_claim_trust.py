"""AG-49: Runtime Claim Trust Index API handlers.

Read endpoints (no operator_id required):
  GET  /api/claim_trust/latest    — latest trust report
  GET  /api/claim_trust/index     — slim trust index
  GET  /api/claim_trust/gaps      — trust gaps
  GET  /api/claim_trust/classes   — per-group trust classes

Write endpoint (operator_id required, 403 without):
  POST /api/claim_trust/run       — trigger trust index run

AG-49 invariant: advisory-only. No governance mutation, no campaign
mutation, no repair execution, no automatic claim correction.
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


async def claim_trust_latest() -> dict[str, Any]:
    """GET /api/claim_trust/latest — latest trust report."""
    try:
        data = _load_json("runtime_claim_trust_latest.json")
        return {"ok": True, "latest": data or {}}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_trust_index() -> dict[str, Any]:
    """GET /api/claim_trust/index — slim trust index."""
    try:
        data = _load_json("runtime_claim_trust_index.json")
        if data is None:
            return {
                "ok": True, "overall_trust_score": None,
                "overall_trust_class": None, "gap_count": 0,
            }
        return {
            "ok":                  True,
            "overall_trust_score": data.get("overall_trust_score"),
            "overall_trust_class": data.get("overall_trust_class"),
            "claim_groups":        data.get("claim_groups", {}),
            "gap_count":           data.get("gap_count", 0),
            "top_gap":             data.get("top_gap"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_trust_gaps() -> dict[str, Any]:
    """GET /api/claim_trust/gaps — trust gaps."""
    try:
        data = _load_json("runtime_claim_trust_latest.json")
        if data is None:
            return {"ok": True, "trust_gaps": [], "gap_count": 0}
        gaps = data.get("trust_gaps", [])
        return {
            "ok":        True,
            "trust_gaps": gaps,
            "gap_count":  len(gaps),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_trust_classes() -> dict[str, Any]:
    """GET /api/claim_trust/classes — per-group trust classes."""
    try:
        data = _load_json("runtime_claim_trust_latest.json")
        if data is None:
            return {"ok": True, "claim_groups": {}, "overall_trust_class": None}
        return {
            "ok":                  True,
            "claim_groups":        data.get("overall", {}).get("claim_groups", {}),
            "overall_trust_class": data.get("overall", {}).get("overall_trust_class"),
            "group_scores":        data.get("overall", {}).get("group_scores", {}),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def claim_trust_run(request: "Request") -> "JSONResponse":
    """POST /api/claim_trust/run — trigger trust index run."""
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
        from runtime.claim_trust_index import run_claim_trust_index
        result = run_claim_trust_index()
        return JSONResponse(status_code=200, content={
            "ok":                  True,
            "triggered_by":        operator_id,
            "overall_trust_class": result["overall_trust_class"],
            "overall_trust_score": result["overall_trust_score"],
            "top_gap":             result["top_gap"],
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "reason": f"trust index failed: {exc}"})


def register_claim_trust_routes(app: Any) -> None:
    """Register AG-49 routes on a FastAPI app instance."""
    app.add_api_route("/api/claim_trust/latest",  claim_trust_latest,  methods=["GET"])
    app.add_api_route("/api/claim_trust/index",   claim_trust_index,   methods=["GET"])
    app.add_api_route("/api/claim_trust/gaps",    claim_trust_gaps,    methods=["GET"])
    app.add_api_route("/api/claim_trust/classes", claim_trust_classes, methods=["GET"])
    app.add_api_route("/api/claim_trust/run",     claim_trust_run,     methods=["POST"])
