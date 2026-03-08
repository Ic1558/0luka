"""Domain logic for BOQ generation."""

from __future__ import annotations


def build_boq_id(project_id: str, drawing_ref: str) -> str:
    """Generate a deterministic BOQ identifier."""

    normalized_drawing = drawing_ref.strip().lower().replace(" ", "-")
    return f"boq-{project_id}-{normalized_drawing}"
