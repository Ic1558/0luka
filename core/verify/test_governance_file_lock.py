from pathlib import Path

from tools.ops.governance_file_lock import (
    build_manifest_payload,
    evaluate_mutation,
    verify_manifest_payload,
)


def test_manifest_build_and_verify(tmp_path: Path):
    root = tmp_path
    (root / "core/governance").mkdir(parents=True)
    (root / "docs/dod").mkdir(parents=True)
    (root / "tools/ops").mkdir(parents=True)

    (root / "core/governance/phase_status.yaml").write_text("phases: {}\n", encoding="utf-8")
    (root / "docs/dod/DOD__PHASE_X.md").write_text("# test\n", encoding="utf-8")
    (root / "tools/ops/dod_checker.py").write_text("print('ok')\n", encoding="utf-8")

    payload = build_manifest_payload(
        root=root,
        specs=("core/governance/**", "docs/dod/**", "tools/ops/dod_checker.py"),
        manifest_rel="core/governance/governance_lock_manifest.json",
        generated_at_utc="2026-02-12T00:00:00Z",
    )
    assert payload["algorithm"] == "sha256"
    assert payload["files"]

    errors = verify_manifest_payload(payload, root)
    assert errors == []


def test_mutation_requires_label_and_manifest_refresh():
    decision = evaluate_mutation(
        changed_files=["core/governance/phase_status.yaml"],
        deleted_files=[],
        labels=[],
        required_label="governance-change",
        manifest_rel="core/governance/governance_lock_manifest.json",
        specs=("core/governance/**",),
    )
    assert not decision.ok
    assert any("without 'governance-change'" in e for e in decision.errors)
    assert any("manifest not updated" in e for e in decision.errors)


def test_mutation_passes_with_label_and_manifest():
    decision = evaluate_mutation(
        changed_files=[
            "core/governance/phase_status.yaml",
            "core/governance/governance_lock_manifest.json",
        ],
        deleted_files=[],
        labels=["governance-change"],
        required_label="governance-change",
        manifest_rel="core/governance/governance_lock_manifest.json",
        specs=("core/governance/**",),
    )
    assert decision.ok
