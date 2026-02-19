from pathlib import Path

from modules.nlp_control_plane.tests.validate_vectors import validate_fixture


def test_phase9_vectors_validate() -> None:
    fixture = Path(__file__).resolve().parents[2] / "modules" / "nlp_control_plane" / "tests" / "phase9_vectors_v0.yaml"
    res = validate_fixture(fixture)
    assert res["ok"] is True, res
    assert res["counts"]["vectors"] == 10, res
    assert res["counts"]["fail_closed"] == 2, res
