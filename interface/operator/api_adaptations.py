"""AG-20: Read-only API endpoints for adaptation records.

Endpoints:
  GET /api/adaptations          — list recent adaptations
  GET /api/adaptations/latest   — latest adaptation record
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def adaptations_list() -> JSONResponse:
    """Return recent adaptation records."""
    try:
        from core.adaptation.adaptation_store import list_recent
        records = list_recent(limit=50)
        return JSONResponse({"adaptations": records, "count": len(records)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def adaptations_latest() -> JSONResponse:
    """Return the latest adaptation record."""
    try:
        from core.adaptation.adaptation_store import get_latest
        record = get_latest()
        if record is None:
            raise HTTPException(status_code=404, detail="no adaptation records found")
        return JSONResponse(record)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
