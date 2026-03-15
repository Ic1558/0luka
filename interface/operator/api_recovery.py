"""AG-28: Read-only API endpoints for recovery records.

Endpoints:
  GET /api/recovery          — list recent recovery records
  GET /api/recovery/latest   — latest recovery record
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def recovery_list() -> JSONResponse:
    """Return recent recovery records."""
    try:
        from core.recovery.recovery_store import list_recent
        records = list_recent(limit=50)
        return JSONResponse({"recoveries": records, "count": len(records)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def recovery_latest() -> JSONResponse:
    """Return the latest recovery record."""
    try:
        from core.recovery.recovery_store import get_latest
        record = get_latest()
        if record is None:
            raise HTTPException(status_code=404, detail="no recovery records found")
        return JSONResponse(record)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
