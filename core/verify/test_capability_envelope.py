"""AG-46: Runtime Capability Envelope — test suite."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


def _make_tmpdir() -> str:
    td = tempfile.mkdtemp()
    os.environ["LUKA_RUNTIME_ROOT"] = td
    (Path(td) / "state").mkdir(parents=True, exist_ok=True)
    return td


class TestCapabilityEnvelope:

    def test_register_capability_writes_valid_jsonl_entry(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        entry = register_capability(
            "drift_intelligence_layer", "AG-37",
            activation_source="runtime_bootstrap",
            notes="Drift intelligence enabled",
            runtime_root=td,
        )
        assert entry["capability_id"] == "drift_intelligence_layer"
        assert entry["component"] == "AG-37"
        assert entry["status"] == "ACTIVE"
        assert "activated_at" in entry
        # Verify persisted
        path = Path(td) / "state" / "runtime_capabilities.jsonl"
        assert path.exists()
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        assert len(rows) == 1
        assert rows[0]["capability_id"] == "drift_intelligence_layer"

    def test_registry_lookup_is_capability_active_true(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        from runtime.capability_registry import is_capability_active
        register_capability("supervised_repair_scheduler", "AG-39", runtime_root=td)
        assert is_capability_active("supervised_repair_scheduler", td) is True

    def test_registry_lookup_is_capability_active_false_when_not_registered(self):
        td = _make_tmpdir()
        from runtime.capability_registry import is_capability_active
        assert is_capability_active("nonexistent_capability", td) is False

    def test_registry_lookup_inactive_capability(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        from runtime.capability_registry import is_capability_active
        register_capability("some_cap", "AG-XX", status="INACTIVE", runtime_root=td)
        assert is_capability_active("some_cap", td) is False

    def test_list_capabilities_returns_all_entries(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        from runtime.capability_registry import list_active_capabilities
        register_capability("cap_a", "AG-37", runtime_root=td)
        register_capability("cap_b", "AG-39", runtime_root=td)
        active = list_active_capabilities(td)
        assert "cap_a" in active
        assert "cap_b" in active

    def test_append_only_cannot_overwrite_previous_entries(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability, list_capabilities
        register_capability("cap_a", "AG-37", status="ACTIVE", runtime_root=td)
        register_capability("cap_a", "AG-37", status="INACTIVE", runtime_root=td)
        entries = list_capabilities(td)
        # Both entries must exist (append-only)
        assert len(entries) == 2
        assert entries[0]["status"] == "ACTIVE"
        assert entries[1]["status"] == "INACTIVE"

    def test_registry_latest_status_wins_for_active(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        from runtime.capability_registry import is_capability_active
        register_capability("cap_a", "AG-37", status="INACTIVE", runtime_root=td)
        register_capability("cap_a", "AG-37", status="ACTIVE",   runtime_root=td)
        assert is_capability_active("cap_a", td) is True

    def test_registry_summary_counts(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        from runtime.capability_registry import registry_summary
        register_capability("cap_a", "AG-37", runtime_root=td)
        register_capability("cap_b", "AG-39", status="INACTIVE", runtime_root=td)
        summary = registry_summary(td)
        assert summary["active_count"] == 1
        assert summary["inactive_count"] == 1
        assert "cap_a" in summary["active"]
        assert "cap_b" in summary["inactive"]

    def test_get_capability_returns_latest(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability, get_capability
        register_capability("cap_a", "AG-37", status="INACTIVE", runtime_root=td)
        register_capability("cap_a", "AG-37", status="ACTIVE",   runtime_root=td)
        entry = get_capability("cap_a", td)
        assert entry is not None
        assert entry["status"] == "ACTIVE"

    def test_get_capability_none_when_not_registered(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import get_capability
        assert get_capability("no_such_cap", td) is None

    def test_register_capability_entry_shape(self):
        td = _make_tmpdir()
        from runtime.capability_envelope import register_capability
        entry = register_capability("repair_campaign_controller", "AG-40", runtime_root=td)
        required_fields = {"capability_id", "component", "activation_source",
                           "activated_at", "status", "notes"}
        assert required_fields.issubset(set(entry.keys()))
