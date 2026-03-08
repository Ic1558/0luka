"""Domain logic for compliance checks."""

from __future__ import annotations


def build_compliance_report_id(project_id: str, boq_id: str, code_set: str) -> str:
    """Generate a deterministic compliance report identifier."""

    return f"cmp-{project_id}-{boq_id}-{code_set}"
