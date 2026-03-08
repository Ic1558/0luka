"""Domain logic for PO generation."""

from __future__ import annotations


def build_po_id(project_id: str, boq_id: str, vendor_profile: str) -> str:
    """Generate a deterministic purchase order identifier."""

    normalized_vendor = vendor_profile.strip().lower().replace(" ", "-")
    return f"po-{project_id}-{boq_id}-{normalized_vendor}"
