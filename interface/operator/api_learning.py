"""AG-21: Read-only API endpoints for learning plane.

Endpoints:
  GET /api/learning/observations       — recent observations
  GET /api/learning/patterns           — pattern registry
  GET /api/learning/policy_candidates  — pending candidates
  GET /api/learning/metrics            — aggregate counts
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def learning_observations() -> JSONResponse:
    try:
        from learning.observation_store import get_recent_observations
        records = get_recent_observations(limit=50)
        return JSONResponse({"observations": records, "count": len(records)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def learning_patterns() -> JSONResponse:
    try:
        from learning.pattern_extractor import get_patterns
        patterns = get_patterns()
        return JSONResponse({"patterns": patterns, "count": len(patterns)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def learning_policy_candidates() -> JSONResponse:
    try:
        from learning.policy_candidates import list_candidates
        candidates = list_candidates(limit=50)
        return JSONResponse({"candidates": candidates, "count": len(candidates)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def learning_metrics() -> JSONResponse:
    try:
        from learning.learning_metrics import get_learning_metrics
        metrics = get_learning_metrics()
        return JSONResponse(metrics)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
