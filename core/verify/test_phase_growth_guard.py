from pathlib import Path

from tools.ops.phase_growth_guard import (
    detect_new_modules_from_diff,
    detect_new_phases_from_diff,
    validate_new_phase,
)


def test_detect_new_phase_from_diff():
    rows = [("A", ["docs/dod/DOD__PHASE_16_0.md"])]
    phases = detect_new_phases_from_diff(rows)
    assert "PHASE_16_0" in phases


def test_validate_new_phase_pass(tmp_path: Path):
    root = tmp_path
    phase_id = "PHASE_16_0"
    (root / "docs/dod").mkdir(parents=True)
    (root / "core/verify").mkdir(parents=True)
    (root / "docs/dod/DOD__PHASE_16_0.md").write_text("# ok\n", encoding="utf-8")
    (root / "core/verify/test_phase_16_0.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (root / "core/verify/prove_phase_16_0.py").write_text("def run():\n    return {}\n", encoding="utf-8")

    result = validate_new_phase(phase_id, root, {"PHASE_16_0"})
    assert result.ok
    assert result.errors == []


def test_validate_new_phase_fail_missing_proof(tmp_path: Path):
    root = tmp_path
    phase_id = "PHASE_16_1"
    (root / "docs/dod").mkdir(parents=True)
    (root / "core/verify").mkdir(parents=True)
    (root / "docs/dod/DOD__PHASE_16_1.md").write_text("# ok\n", encoding="utf-8")
    (root / "core/verify/test_phase_16_1.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = validate_new_phase(phase_id, root, {"PHASE_16_1"})
    assert not result.ok
    assert any("proof_harness" in err for err in result.errors)


def test_detect_new_module_name_from_diff():
    rows = [("A", ["modules/new_module/README.md"])]
    modules = detect_new_modules_from_diff(rows)
    assert "new_module" in modules
