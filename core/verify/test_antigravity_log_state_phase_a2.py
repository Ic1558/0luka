from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_phase_a2_normalized_observability_and_state_paths_exist() -> None:
    expected = [
        ROOT / "observability" / "logs" / "antigravity" / "README.md",
        ROOT / "runtime" / "state" / "antigravity" / "README.md",
        ROOT / "runtime" / "services" / "antigravity_bootstrap" / "pm2_start.zsh",
        ROOT / "runtime" / "services" / "antigravity_scan" / "runner.zsh",
        ROOT / "runtime" / "services" / "antigravity_realtime" / "runner.zsh",
    ]
    for path in expected:
        assert path.exists(), f"missing normalized ownership path: {path}"


def test_phase_a2_scan_runner_normalizes_logs_and_runtime_state() -> None:
    text = _read("runtime/services/antigravity_scan/runner.zsh")

    assert 'OBS_DIR="$ROOT_DIR/observability/logs/antigravity"' in text
    assert 'STATE_DIR="$ROOT_DIR/runtime/state/antigravity"' in text
    assert 'ln -sfn "$OBS_DIR" "$APP_DIR/logs"' in text
    assert "antigravity_scan_runtime.json" in text
    assert "canonical_log_path" in text


def test_phase_a2_realtime_runner_normalizes_logs_and_runtime_state() -> None:
    text = _read("runtime/services/antigravity_realtime/runner.zsh")

    assert 'OBS_DIR="$ROOT_DIR/observability/logs/antigravity"' in text
    assert 'STATE_DIR="$ROOT_DIR/runtime/state/antigravity"' in text
    assert 'ln -sfn "$OBS_DIR" "$APP_DIR/logs"' in text
    assert "antigravity_realtime_runtime.json" in text
    assert "canonical_stdout_path" in text
    assert "canonical_stderr_path" in text


def test_phase_a2_bootstrap_writes_pm2_logs_to_observability_and_state() -> None:
    text = _read("runtime/services/antigravity_bootstrap/pm2_start.zsh")

    assert 'OBS_DIR="$ROOT_DIR/observability/logs/antigravity"' in text
    assert 'STATE_DIR="$ROOT_DIR/runtime/state/antigravity"' in text
    assert "bootstrap_state.json" in text
    assert "--output \"$OBS_DIR/antigravity_monitor.out.log\"" in text
    assert "--error \"$OBS_DIR/antigravity_monitor.err.log\"" in text
    assert "--output \"$OBS_DIR/option_bug_hunter.out.log\"" in text
    assert "--error \"$OBS_DIR/option_bug_hunter.err.log\"" in text


def test_phase_a2_docs_mark_legacy_paths_as_transitional_not_truth() -> None:
    observability_text = _read("observability/logs/antigravity/README.md")
    runtime_text = _read("runtime/state/antigravity/README.md")
    handoff_text = _read("modules/antigravity/docs/PHASE_A_KERNELIZATION_HANDOFF.md")

    assert "operational source of truth" in observability_text
    assert "transitional only" in observability_text
    assert "runtime state is mutable current service state only" in runtime_text
    assert "Legacy repo-local log paths may still exist as transitional compatibility adapters" in handoff_text


def test_phase_a2_no_new_feature_or_secret_expansion_in_wrappers() -> None:
    scan_text = _read("runtime/services/antigravity_scan/runner.zsh").lower()
    realtime_text = _read("runtime/services/antigravity_realtime/runner.zsh").lower()
    bootstrap_text = _read("runtime/services/antigravity_bootstrap/pm2_start.zsh").lower()

    for text in (scan_text, realtime_text, bootstrap_text):
        assert "telegram_bot_token=" not in text
        assert "new scanner" not in text
        assert "new feature" not in text
