"""AG-P5: Tool Registry — static registration of callable tools."""
from __future__ import annotations

_TOOLS: dict[str, dict] = {}


def register_tool(name: str, fn, *, description: str = "", schema: dict | None = None) -> None:
    """Register a callable tool by name."""
    _TOOLS[name] = {
        "name": name,
        "fn": fn,
        "description": description,
        "schema": schema or {},
    }


def get_tool(name: str) -> dict | None:
    """Return tool entry or None if not registered."""
    return _TOOLS.get(name)


def list_tools() -> list[str]:
    return list(_TOOLS.keys())
