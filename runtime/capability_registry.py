"""AG-46: Runtime Capability Registry.

Read-only lookup layer over the capability envelope JSONL.
No writes allowed in this layer.
"""
from __future__ import annotations

import os
from typing import Any

from runtime.capability_envelope import list_capabilities


def is_capability_active(
    capability_id: str,
    runtime_root: str | None = None,
) -> bool:
    """Return True if the most recent entry for capability_id has status ACTIVE."""
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    entries = list_capabilities(rt)
    # Last entry for this capability_id wins
    status = None
    for entry in entries:
        if entry.get("capability_id") == capability_id:
            status = entry.get("status")
    return status == "ACTIVE"


def list_active_capabilities(runtime_root: str | None = None) -> list[str]:
    """Return list of capability_ids that are currently ACTIVE.

    When a capability is registered multiple times, the most recent
    status entry determines whether it is active.
    """
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    entries = list_capabilities(rt)
    # Build latest status per capability_id
    latest: dict[str, str] = {}
    for entry in entries:
        cid    = entry.get("capability_id", "")
        status = entry.get("status", "")
        if cid:
            latest[cid] = status
    return [cid for cid, st in latest.items() if st == "ACTIVE"]


def registry_summary(runtime_root: str | None = None) -> dict[str, Any]:
    """Return a summary of all registered capabilities and their statuses."""
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    entries = list_capabilities(rt)
    # Latest entry per capability_id
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        cid = entry.get("capability_id", "")
        if cid:
            latest[cid] = entry

    active   = [e for e in latest.values() if e.get("status") == "ACTIVE"]
    inactive = [e for e in latest.values() if e.get("status") != "ACTIVE"]

    return {
        "total_registered": len(latest),
        "active_count":     len(active),
        "inactive_count":   len(inactive),
        "active":           [e["capability_id"] for e in active],
        "inactive":         [e["capability_id"] for e in inactive],
        "all":              list(latest.values()),
    }
