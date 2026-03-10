from __future__ import annotations

from pathlib import Path


TEMPLATE = Path("/Users/icmini/0luka/interface/operator/templates/mission_control.html").read_text(encoding="utf-8")


def test_proof_consumption_section_is_present() -> None:
    assert "Proof Consumption" in TEMPLATE
    assert 'id="proof-artifact-panel"' in TEMPLATE
    assert 'id="qs-run-panel"' in TEMPLATE
    assert 'id="qs-run-artifacts-panel"' in TEMPLATE
    assert "No proof artifacts loaded" in TEMPLATE
    assert "No QS runs detected" in TEMPLATE
    assert "No linked artifacts available" in TEMPLATE


def test_proof_consumption_fetch_wiring_is_present() -> None:
    assert "fetch('/api/proof_artifacts?limit=8')" in TEMPLATE
    assert "fetch('/api/qs_runs?limit=8')" in TEMPLATE
    assert "'/api/qs_runs/' + encodeURIComponent(safeRunId) + '/artifacts'" in TEMPLATE
