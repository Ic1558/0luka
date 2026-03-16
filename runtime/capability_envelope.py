"""AG-46: Runtime Capability Envelope.

Records active runtime capabilities as append-only JSONL entries.
Pure observation — no execution path changes, no governance mutation.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _rt(runtime_root: str | None = None) -> str:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    return rt


def _capabilities_path(runtime_root: str | None = None) -> Path:
    return Path(_rt(runtime_root)) / "state" / "runtime_capabilities.jsonl"


def register_capability(
    capability_id: str,
    component: str,
    activation_source: str = "runtime_bootstrap",
    status: str = "ACTIVE",
    notes: str = "",
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Append a capability registration entry to the envelope JSONL.

    Fields:
      capability_id     — unique capability identifier (e.g. "drift_intelligence_layer")
      component         — AG phase that owns this capability (e.g. "AG-37")
      activation_source — how it was activated ("runtime_bootstrap", "operator_trigger", etc.)
      activated_at      — ISO-8601 UTC timestamp
      status            — "ACTIVE" | "INACTIVE" | "DEGRADED"
      notes             — free-form description

    Append-only — never overwrites existing entries.
    Returns the written entry.
    """
    entry: dict[str, Any] = {
        "capability_id":    capability_id,
        "component":        component,
        "activation_source": activation_source,
        "activated_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status":           status,
        "notes":            notes,
    }
    path = _capabilities_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def list_capabilities(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all capability entries from the envelope JSONL (oldest first)."""
    path = _capabilities_path(runtime_root)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entries.append(json.loads(raw))
        except Exception:
            continue
    return entries


def get_capability(
    capability_id: str,
    runtime_root: str | None = None,
) -> dict[str, Any] | None:
    """Return the most recent entry for a given capability_id, or None."""
    entries = list_capabilities(runtime_root)
    # Return last occurrence (latest registration wins)
    result = None
    for entry in entries:
        if entry.get("capability_id") == capability_id:
            result = entry
    return result
