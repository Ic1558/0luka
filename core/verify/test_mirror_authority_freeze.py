"""Tests — Legacy Mirror Retirement Phase 3: Authority Freeze.

Verifies that assert_mirror_consistency raises RuntimeError('mirror_authority_violation')
when mirror fields diverge from execution_envelope values, and is a no-op when they agree
or when no envelope is present.
"""

from __future__ import annotations

import pytest

from core.result_integrity import assert_mirror_consistency


def _result_with_envelope(
    mirror_status: str = "ok",
    mirror_summary: str = "done",
    env_status: str = "ok",
    env_summary: str = "done",
) -> dict:
    return {
        "status": mirror_status,
        "summary": mirror_summary,
        "execution_envelope": {
            "result": {
                "status": env_status,
                "summary": env_summary,
            }
        },
    }


# --- PASS cases ---

def test_mirrors_match_envelope_passes() -> None:
    """PASS: mirror fields agree with envelope — no exception raised."""
    result = _result_with_envelope(
        mirror_status="ok", mirror_summary="done",
        env_status="ok", env_summary="done",
    )
    assert_mirror_consistency(result)  # must not raise


def test_no_envelope_is_exempt() -> None:
    """PASS: pre-envelope results (no execution_envelope) are exempt from check."""
    result = {"status": "ok", "summary": "done"}
    assert_mirror_consistency(result)  # must not raise


def test_empty_mirror_status_not_a_violation() -> None:
    """PASS: empty/falsy mirror status is not flagged — only non-empty conflicts count."""
    result = {
        "status": "",
        "summary": "",
        "execution_envelope": {
            "result": {"status": "ok", "summary": "done"},
        },
    }
    assert_mirror_consistency(result)  # must not raise


def test_envelope_with_empty_result_section_passes() -> None:
    """PASS: envelope with no result section — nothing to compare, no violation."""
    result = {
        "status": "ok",
        "summary": "done",
        "execution_envelope": {},
    }
    assert_mirror_consistency(result)  # must not raise


# --- FAIL cases ---

def test_status_mismatch_raises() -> None:
    """FAIL: mirror status != envelope status → RuntimeError."""
    result = _result_with_envelope(mirror_status="error", env_status="ok")
    with pytest.raises(RuntimeError, match="mirror_authority_violation"):
        assert_mirror_consistency(result)


def test_summary_mismatch_raises() -> None:
    """FAIL: mirror summary != envelope summary → RuntimeError."""
    result = _result_with_envelope(mirror_summary="old summary", env_summary="new summary")
    with pytest.raises(RuntimeError, match="mirror_authority_violation"):
        assert_mirror_consistency(result)


def test_error_message_names_field() -> None:
    """FAIL: error message identifies which field diverged."""
    result = _result_with_envelope(mirror_status="rejected", env_status="ok")
    with pytest.raises(RuntimeError) as exc_info:
        assert_mirror_consistency(result)
    assert "status" in str(exc_info.value)
    assert "mirror_authority_violation" in str(exc_info.value)
