#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skills" / "manifest.md"

REQUIRED_SKILLS = {
    "notebooklm_grounding": "YES",
    "knowledge_recycling": "YES",
    "asset_fragment_manager": "NO",
}


def _find_row(skill_id: str, text: str) -> str:
    for line in text.splitlines():
        if f"`{skill_id}`" in line and "|" in line:
            return line
    raise AssertionError(f"missing_manifest_row:{skill_id}")


def test_manifest_exists() -> None:
    assert MANIFEST.exists(), f"missing:{MANIFEST}"


def test_manifest_has_required_columns() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    header = "| skill_id | purpose | Mandatory Read | MCPs used | Inputs | Outputs | Caps | Forbidden actions |"
    assert header in text, "missing_phase15_header"


def test_mandatory_read_detectable() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    for skill_id, expected in REQUIRED_SKILLS.items():
        row = _find_row(skill_id, text)
        assert f"| {expected} |" in row, f"mandatory_read_mismatch:{skill_id}:{row}"


def test_skill_files_exist() -> None:
    for skill_id in REQUIRED_SKILLS:
        skill_path = ROOT / "skills" / skill_id / "SKILL.md"
        assert skill_path.exists(), f"missing:{skill_path}"
        body = skill_path.read_text(encoding="utf-8")
        assert "## Caps" in body, f"missing_caps:{skill_id}"
        assert "## Forbidden" in body, f"missing_forbidden:{skill_id}"


def test_chain_contract_documented() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    assert "## Chained Load Contract" in text
    assert "Mandatory Read: YES" in text


if __name__ == "__main__":
    tests = [
        test_manifest_exists,
        test_manifest_has_required_columns,
        test_mandatory_read_detectable,
        test_skill_files_exist,
        test_chain_contract_documented,
    ]
    for test in tests:
        test()
    print("test_phase15_skill_os: all ok")
