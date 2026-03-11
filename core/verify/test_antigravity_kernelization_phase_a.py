from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase_a_kernel_ownership_paths_exist() -> None:
    expected = [
        ROOT / "core" / "governance" / "secrets_policy.md",
        ROOT / "runtime" / "supervisors" / "ANTIGRAVITY_RUNTIME_OWNERSHIP.md",
        ROOT / "runtime" / "services" / "README.md",
        ROOT / "observability" / "logs" / "antigravity" / "README.md",
        ROOT / "modules" / "antigravity" / "README.md",
        ROOT / "modules" / "antigravity" / "intelligence" / "README.md",
        ROOT / "modules" / "antigravity" / "realtime" / "README.md",
        ROOT / "modules" / "antigravity" / "connectors" / "README.md",
        ROOT / "modules" / "antigravity" / "infra" / "README.md",
        ROOT / "modules" / "antigravity" / "docs" / "PHASE_A_KERNELIZATION_HANDOFF.md",
    ]
    for path in expected:
        assert path.exists(), f"missing expected kernelization path: {path}"


def test_phase_a_secrets_policy_promotes_kernel_secret_rules() -> None:
    text = (ROOT / "core" / "governance" / "secrets_policy.md").read_text(encoding="utf-8")

    assert "dotenvx" in text
    assert ".env.local" in text
    assert ".env.keys" in text
    assert "must never be committed" in text
    assert "belongs to 0luka core governance" in text


def test_phase_a_runtime_and_observability_ownership_are_kernel_anchored() -> None:
    runtime_text = (ROOT / "runtime" / "supervisors" / "ANTIGRAVITY_RUNTIME_OWNERSHIP.md").read_text(encoding="utf-8")
    observability_text = (ROOT / "observability" / "logs" / "antigravity" / "README.md").read_text(encoding="utf-8")

    assert "runtime/supervisors/" in runtime_text
    assert "repos/option/tools/deploy_prod.sh" in runtime_text
    assert "system survival" in runtime_text
    assert "observability/logs/antigravity/" in observability_text
    assert "source-of-truth ownership boundary" in observability_text


def test_phase_a_existing_antigravity_entrypoints_remain_discoverable() -> None:
    expected = [
        ROOT / "repos" / "option" / "tools" / "deploy_prod.sh",
        ROOT / "repos" / "option" / "src" / "antigravity_prod.py",
        ROOT / "repos" / "option" / "src" / "live.js",
        ROOT / "system" / "antigravity" / "scripts" / "dispatch_latest.zsh",
    ]
    for path in expected:
        assert path.exists(), f"missing existing Antigravity entrypoint: {path}"


def test_phase_a_deploy_reference_still_uses_dotenvx_and_pm2_without_new_feature_drift() -> None:
    text = (ROOT / "repos" / "option" / "tools" / "deploy_prod.sh").read_text(encoding="utf-8")

    assert "dotenvx run" in text
    assert "pm2 start" in text
    assert "Antigravity-Monitor" in text
    assert "OptionBugHunter" in text


def test_phase_a_handoff_doc_marks_antigravity_as_module_not_host() -> None:
    text = (ROOT / "modules" / "antigravity" / "docs" / "PHASE_A_KERNELIZATION_HANDOFF.md").read_text(encoding="utf-8")

    assert "What Moved Into 0luka Ownership" in text
    assert "What Remains In Antigravity Module Space" in text
    assert "Intentionally Deferred" in text
    assert "feature work is frozen" in text
