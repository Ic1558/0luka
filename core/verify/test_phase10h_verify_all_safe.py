from pathlib import Path

ROOT = Path("/Users/icmini/0luka")

def test_verify_all_safe_exists():
    p = ROOT / "tools/ops/verify_all_safe.zsh"
    assert p.exists(), "verify_all_safe.zsh missing"
    txt = p.read_text(encoding="utf-8")
    assert "safe_run.zsh" in txt, "verify_all_safe must delegate gating to safe_run"

def test_phase9_vectors_canonical_points_to_verify_all_safe():
    # Phase10H invariant: canonical verify entrypoints MUST funnel to verify_all_safe
    # NOTE: do NOT assert inside phase9_vectors_v0.yaml (it is taxonomy/vectors, not the canonical command surface).
    files = [
        ROOT / "modules/nlp_control_plane/tests/validate_vectors.py",
        ROOT / "modules/nlp_control_plane/specs/phase9_linguist_mapping_v0.md",
        ROOT / "core/runtime_lane.py",
    ]
    for fp in files:
        s = fp.read_text(encoding="utf-8")
        assert "verify_all_safe.zsh" in s, f"expected verify_all_safe reference in {fp}"

