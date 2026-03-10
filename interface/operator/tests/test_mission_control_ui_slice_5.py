from __future__ import annotations

from pathlib import Path


TEMPLATE = Path("/tmp/run-interpretation-ui/interface/operator/templates/mission_control.html").read_text(encoding="utf-8")


def _proof_consumption_section() -> str:
    marker = "<h2>Proof Consumption</h2>"
    start = TEMPLATE.index(marker)
    end = TEMPLATE.index("</section>", start)
    return TEMPLATE[start:end]


def test_run_interpretation_signal_hooks_are_present() -> None:
    section = _proof_consumption_section()
    assert "proof-signal" in TEMPLATE
    assert "Signal unavailable" in TEMPLATE
    assert "artifact_count=" in TEMPLATE
    assert "expected_artifacts=" in TEMPLATE
    assert "missing_artifacts=" in TEMPLATE
    assert 'id="qs-run-panel"' in section


def test_proof_consumption_section_keeps_safe_read_only_rendering() -> None:
    section = _proof_consumption_section()
    assert "No QS runs detected" in section
    assert "No linked artifacts available" in section
    assert "<button" not in section
