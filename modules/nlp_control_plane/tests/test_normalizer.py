"""
Unit Tests for NLP Normalizer
=============================
"""

import pytest
from ..core.normalizer import normalize_input, build_task_spec, INTENT_PATTERNS


class TestNormalizeInput:
    """Test normalize_input function."""

    def test_liam_status_check(self):
        """Test 'liam check status' pattern."""
        result = normalize_input("liam check status")
        assert result["intent"] == "status_check"
        assert result["tool"] == "status_reader"
        assert result["risk"] == "low"

    def test_status_check_variations(self):
        """Test various status check patterns."""
        for text in ["check status", "show status", "get status"]:
            result = normalize_input(text)
            assert result["intent"] == "status_check", f"Failed for: {text}"

    def test_session_start(self):
        """Test session start patterns."""
        result = normalize_input("liam session start")
        assert result["intent"] == "session_start"
        assert result["risk"] == "low"

    def test_task_list(self):
        """Test task listing patterns."""
        for text in ["show tasks", "list pending", "list inbox"]:
            result = normalize_input(text)
            assert result["intent"] == "task_list", f"Failed for: {text}"

    def test_high_risk_execution(self):
        """Test high-risk execution patterns."""
        result = normalize_input("lisa run deploy")
        assert result["intent"] == "task_execution"
        assert result["risk"] == "high"

    def test_unknown_fallback(self):
        """Test unknown patterns fallback to high risk."""
        result = normalize_input("do something random xyz")
        assert result["intent"] == "unknown"
        assert result["risk"] == "high"

    def test_preserves_raw_input(self):
        """Test that raw input is preserved in params."""
        raw = "LIAM Check Status"
        result = normalize_input(raw)
        assert result["params"]["raw"] == raw


class TestBuildTaskSpec:
    """Test build_task_spec function."""

    def test_task_spec_structure(self):
        """Test TaskSpec structure is correct."""
        normalized = {
            "intent": "status_check",
            "tool": "status_reader",
            "risk": "low",
            "params": {"raw": "check status"},
            "matched_pattern": ".*"
        }
        preview_id = "test-preview-123"
        spec = build_task_spec(normalized, preview_id)

        # Check required fields
        assert "task_id" in spec
        assert spec["task_id"].startswith("task_")
        assert spec["author"] == "gmx"
        assert spec["intent"] == "status_check"
        assert "operations" in spec
        assert len(spec["operations"]) == 1
        assert "created_at_utc" in spec
        assert spec["preview_id"] == preview_id

    def test_low_risk_lane(self):
        """Test low risk maps to task lane."""
        normalized = {"intent": "test", "tool": "test", "risk": "low", "params": {}}
        spec = build_task_spec(normalized, "test")
        assert spec["lane"] == "task"

    def test_high_risk_lane(self):
        """Test high risk maps to approval lane."""
        normalized = {"intent": "test", "tool": "test", "risk": "high", "params": {}}
        spec = build_task_spec(normalized, "test")
        assert spec["lane"] == "approval"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
