#!/usr/bin/env python3
"""Phase 11B regression test — ensures clec_v1.yaml is present in tmproot after ensure_test_root."""
from __future__ import annotations

import tempfile
from pathlib import Path


def test_clec_v1_schema_present_in_tmproot(tmp_path: Path) -> None:
    """ensure_test_root must copy clec_v1.yaml into the tmp root's interface/schemas/."""
    from core.verify._test_root import ensure_test_root

    ensure_test_root(tmp_path)
    schema_path = tmp_path / "interface" / "schemas" / "clec_v1.yaml"
    assert schema_path.exists(), f"clec_v1.yaml missing from tmproot after ensure_test_root: {schema_path}"
    # Sanity: must be a non-empty YAML file
    content = schema_path.read_text(encoding="utf-8")
    assert len(content) > 10, "clec_v1.yaml appears empty"
    print("test_clec_v1_schema_present_in_tmproot: ok")
