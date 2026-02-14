from pathlib import Path

from modules.email_orchestration.evidence import evidence_paths, write_json, write_parsed_yaml, write_raw_eml


def test_evidence_paths_and_atomic_writes(tmp_path: Path):
    paths = evidence_paths(tmp_path, "task-1", day="20260213")
    digest = write_raw_eml(paths, b"raw-email")
    write_parsed_yaml(paths, "ring: R1\n")
    write_json(paths, "verdict", {"ok": True})
    write_json(paths, "result", {"exit_code": 0})

    assert paths["eml"].exists()
    assert paths["parsed"].exists()
    assert paths["verdict"].exists()
    assert paths["result"].exists()
    assert paths["sha256"].exists()
    assert len(digest) == 64
