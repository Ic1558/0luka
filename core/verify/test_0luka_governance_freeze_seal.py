#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "core" / "governance" / "0luka_platform_frozen_manifest.yaml"
DOC_PATH = ROOT / "docs" / "governance" / "FREEZE_0LUKA_PLATFORM_v1.md"


def _load_manifest() -> dict:
    payload = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "freeze manifest must be a YAML object"
    return payload


def test_freeze_manifest_exists_and_is_partial_until_tagged() -> None:
    manifest = _load_manifest()
    assert manifest["freeze_id"] == "0luka-platform-v1"
    assert manifest["status"] == "PARTIAL_FREEZE_ACTIVE"
    assert manifest["baseline"]["tag_required"] is True
    assert manifest["baseline"]["tag_status"] == "pending"


def test_freeze_manifest_declares_frozen_interfaces_and_change_control() -> None:
    manifest = _load_manifest()
    frozen = manifest.get("frozen_interfaces")
    assert isinstance(frozen, list) and frozen, "frozen_interfaces must be non-empty"
    names = {row["name"] for row in frozen}
    assert "qs_job_registry_entrypoint" in names
    assert "qs_runtime_sidecar" in names
    assert "qs_mission_control_projection" in names
    assert "activity_feed_chain" in names
    assert "runtime_validator_cli" in names
    assert "runtime_guardian_safe_actions" in names

    control = manifest.get("change_control")
    assert isinstance(control, dict)
    required = set(control.get("requires_for_interface_change", []))
    assert {"ADR", "proof_backed_tests", "docs_update", "compatibility_note"} <= required


def test_freeze_manifest_declares_compatibility_invariants() -> None:
    manifest = _load_manifest()
    compatibility = manifest.get("compatibility_rules")
    assert isinstance(compatibility, dict)
    assert compatibility["identity_fields_immutable"] == ["run_id", "job_type", "project_id"]
    assert compatibility["guardian_safe_action_values"] == ["none", "report_only", "freeze_and_alert"]
    assert compatibility["interface_changes"]["renames_allowed"] is False
    assert compatibility["interface_changes"]["semantic_redefinition_allowed"] is False


def test_freeze_doc_exists_and_references_manifest() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "PARTIAL_FREEZE_ACTIVE" in content
    assert "core/governance/0luka_platform_frozen_manifest.yaml" in content
    assert "baseline git tag creation" in content
