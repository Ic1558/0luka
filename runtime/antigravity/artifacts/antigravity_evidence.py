"""Antigravity evidence artifact model.

Reference-only data model. No file reads, parsing, or runtime probing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AntigravityEvidence:
    """Structured reference to evidence used in runtime analysis."""

    evidence_id: str
    evidence_type: str
    source: str
    timestamp: str
    reference_path: str
    notes: str = ""
