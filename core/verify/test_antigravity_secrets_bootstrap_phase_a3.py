from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_phase_a3_bootstrap_contract_paths_exist() -> None:
    expected = [
        ROOT / "core" / "governance" / "secrets_policy.md",
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "README.md",
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "bootstrap_contract.md",
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "env_contract.md",
    ]
    for path in expected:
        assert path.exists(), f"missing Phase A.3 contract path: {path}"


def test_phase_a3_secrets_policy_remains_authoritative_for_antigravity() -> None:
    text = _read("core/governance/secrets_policy.md")

    assert "Antigravity is one consumer of" in text
    assert "not the owner of it" in text
    assert "runtime/services/antigravity_bootstrap/" in text
    assert "env_contract.md" in text
    assert "bootstrap_contract.md" in text


def test_phase_a3_env_contract_documents_names_only_without_secret_values() -> None:
    text = _read("runtime/services/antigravity_bootstrap/env_contract.md")

    for name in (
        "SETTRADE_APP_ID",
        "SETTRADE_APP_SECRET",
        "SETTRADE_BROKER_ID",
        "SETTRADE_APP_CODE",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "SETTRADE_PRODUCT",
        "SETTRADE_EXPIRY",
        "SETTRADE_STRIKES",
        "MIN_PROFIT",
        "COMMISSION",
        "WS_URL",
        "SETTRADE_MODE",
        "FIRECRAWL_API_KEY",
    ):
        assert name in text

    assert "must never contain secret values" in text
    assert "new production variables require governance review" in text
    assert "sk_" not in text.lower()
    assert "token=" not in text.lower()


def test_phase_a3_bootstrap_wrapper_points_to_governance_and_runtime_contracts() -> None:
    readme_text = _read("runtime/services/antigravity_bootstrap/README.md")
    wrapper_text = _read("runtime/services/antigravity_bootstrap/pm2_start.zsh")

    assert "core/governance/secrets_policy.md" in readme_text
    assert "bootstrap_contract.md" in readme_text
    assert "env_contract.md" in readme_text
    assert "Secret handling authority" in wrapper_text
    assert "bootstrap_contract.md" in wrapper_text


def test_phase_a3_handoff_doc_marks_antigravity_as_non_authoritative_for_bootstrap() -> None:
    text = _read("modules/antigravity/docs/PHASE_A_KERNELIZATION_HANDOFF.md")

    assert "Phase A.3 Secrets / Bootstrap Standardization" in text
    assert "0luka core governance owns secrets law" in text
    assert "0luka runtime owns bootstrap and environment contract visibility" in text
    assert "Legacy repo-local bootstrap assumptions remain delegated only" in text
