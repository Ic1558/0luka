from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_phase_a1_runtime_wrapper_paths_exist() -> None:
    expected = [
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "README.md",
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "pm2_start.zsh",
        ROOT / "runtime" / "services" / "antigravity_scan" / "README.md",
        ROOT / "runtime" / "services" / "antigravity_scan" / "runner.zsh",
        ROOT / "runtime" / "services" / "antigravity_realtime" / "README.md",
        ROOT / "runtime" / "services" / "antigravity_realtime" / "runner.zsh",
    ]
    for path in expected:
        assert path.exists(), f"missing runtime wrapper path: {path}"


def test_phase_a1_runtime_wrappers_delegate_to_existing_implementations() -> None:
    scan_runner = _read("runtime/services/antigravity_scan/runner.zsh")
    realtime_runner = _read("runtime/services/antigravity_realtime/runner.zsh")

    assert "repos/option" in scan_runner
    assert "dotenvx run -- ./venv/bin/python3 src/antigravity_prod.py" in scan_runner

    assert "repos/option" in realtime_runner
    assert "dotenvx run -- node src/live.js" in realtime_runner


def test_phase_a1_runtime_bootstrap_uses_runtime_owned_wrappers() -> None:
    bootstrap = _read("runtime/services/antigravity_bootstrap/pm2_start.zsh")

    assert "runtime/services/antigravity_scan/runner.zsh" in bootstrap
    assert "runtime/services/antigravity_realtime/runner.zsh" in bootstrap
    assert 'pm2 start "$SCAN_RUNNER"' in bootstrap
    assert 'pm2 start "$REALTIME_RUNNER"' in bootstrap


def test_phase_a1_supervisor_doc_records_wrapper_mapping() -> None:
    text = _read("runtime/supervisors/ANTIGRAVITY_RUNTIME_OWNERSHIP.md")

    assert "Phase A.1 Runtime Wrapper Mapping" in text
    assert "Antigravity-Monitor" in text
    assert "OptionBugHunter" in text
    assert "runtime/services/antigravity_bootstrap/pm2_start.zsh" in text
    assert "runtime/services/antigravity_scan/runner.zsh" in text
    assert "runtime/services/antigravity_realtime/runner.zsh" in text


def test_phase_a1_handoff_doc_marks_wrapper_first_ownership() -> None:
    text = _read("modules/antigravity/docs/PHASE_A_KERNELIZATION_HANDOFF.md")

    assert "Phase A.1 Runtime Entrypoint Relocation" in text
    assert "runtime/services/antigravity_bootstrap/pm2_start.zsh" in text
    assert "runtime/services/antigravity_scan/runner.zsh" in text
    assert "runtime/services/antigravity_realtime/runner.zsh" in text


def test_phase_a1_relocation_does_not_expand_secrets_or_features() -> None:
    scan_runner = _read("runtime/services/antigravity_scan/runner.zsh")
    realtime_runner = _read("runtime/services/antigravity_realtime/runner.zsh")
    bootstrap = _read("runtime/services/antigravity_bootstrap/pm2_start.zsh")

    assert "export " not in scan_runner
    assert "export " not in realtime_runner
    assert "new scanner" not in bootstrap.lower()
    assert "new feature" not in bootstrap.lower()
