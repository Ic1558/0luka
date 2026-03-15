"""AG-18: Read-only decision API surfaces.

Exposes three endpoints:
  GET /api/decisions            — recent decision records (append log)
  GET /api/decisions/latest     — latest single decision record
  GET /api/operator/inbox       — recent operator escalation cases

Usage A — standalone (runs on port 7011 by default):
  python3 -m interface.operator.api_decisions

Usage B — register into an existing Starlette app:
  from interface.operator.api_decisions import routes
  for route in routes:
      app.add_route(route.path, route.endpoint, methods=route.methods)

No mutate, no action, no control endpoints.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    _STARLETTE = True
except ImportError:
    _STARLETTE = False

from core.decision import decision_store
from core.operator.operator_queue import list_operator_cases

_DEFAULT_PORT = 7011


# ---------------------------------------------------------------------------
# Endpoint handlers
# ---------------------------------------------------------------------------

def _get_limit(request: Any, default: int = 50, max_val: int = 200) -> int:
    try:
        return min(int(request.query_params.get("limit", default)), max_val)
    except (TypeError, ValueError):
        return default


async def decisions_list(request: Any) -> Any:
    """GET /api/decisions — recent decision records."""
    limit = _get_limit(request)
    try:
        items = decision_store.list_recent(limit=limit)
        return JSONResponse({"ok": True, "count": len(items), "items": items})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


async def decisions_latest(request: Any) -> Any:
    """GET /api/decisions/latest — latest decision record."""
    try:
        record = decision_store.get_latest()
        if record is None:
            return JSONResponse({"ok": True, "record": None})
        return JSONResponse({"ok": True, "record": record})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


async def operator_inbox(request: Any) -> Any:
    """GET /api/operator/inbox — recent operator escalation cases."""
    limit = _get_limit(request)
    try:
        items = list_operator_cases(limit=limit)
        return JSONResponse({"ok": True, "count": len(items), "items": items})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Route table — importable for embedding in other Starlette apps
# ---------------------------------------------------------------------------

if _STARLETTE:
    routes = [
        Route("/api/decisions", decisions_list, methods=["GET"]),
        Route("/api/decisions/latest", decisions_latest, methods=["GET"]),
        Route("/api/operator/inbox", operator_inbox, methods=["GET"]),
    ]
else:
    routes = []


# ---------------------------------------------------------------------------
# Standalone entrypoint
# ---------------------------------------------------------------------------

def create_app() -> Any:
    if not _STARLETTE:
        raise ImportError("starlette is required to run api_decisions standalone")
    return Starlette(routes=routes)


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("uvicorn required: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    port = int(os.environ.get("AG18_API_PORT", _DEFAULT_PORT))
    print(f"AG-18 Decision API running on http://127.0.0.1:{port}")
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
