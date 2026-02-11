#!/usr/bin/env python3
import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "skills" / "pattern-killer" / "scripts" / "pattern_killer.py"
PATTERNS = REPO_ROOT / "skills" / "pattern-killer" / "references" / "patterns.jsonl"


def _run(args, input_text=None):
    proc = subprocess.run(
        ["python3", str(CLI), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def test_detect_finds_matches_deterministically():
    text = "We utilize tools in order to move very very fast."
    rc, out, err = _run(["detect", "--patterns", str(PATTERNS)], input_text=text)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["command"] == "detect"
    assert payload["match_count"] >= 3
    assert payload["matched_pattern_ids"] == sorted(payload["matched_pattern_ids"])


def test_rewrite_supports_empty_replacement_deterministically():
    text = "actually this is actually fine"
    rc, out, err = _run(["rewrite", "--patterns", str(PATTERNS)], input_text=text)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["command"] == "rewrite"
    assert "actually" not in payload["rewritten_text"]


def test_score_is_stable():
    text = "utilize in order to very very"
    rc1, out1, err1 = _run(["score", "--patterns", str(PATTERNS)], input_text=text)
    rc2, out2, err2 = _run(["score", "--patterns", str(PATTERNS)], input_text=text)
    assert rc1 == 0 and rc2 == 0, f"{err1} {err2}"
    p1 = json.loads(out1)
    p2 = json.loads(out2)
    assert p1["score"] == p2["score"]
    assert isinstance(p1["score"], float)


def test_schema_validation_rejects_bad_jsonl_lines():
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.jsonl"
        bad.write_text('{"id":"x"}\n', encoding="utf-8")
        rc, _out, err = _run(["detect", "--patterns", str(bad)], input_text="hi")
        assert rc != 0
        assert "invalid_pattern_line" in err


def test_e2e_detect_rewrite_score_apply():
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "input.txt"
        out_file = Path(td) / "rewritten.txt"
        src.write_text("We utilize this in order to actually move very very fast.", encoding="utf-8")

        rc_d, out_d, err_d = _run(["detect", "--patterns", str(PATTERNS), "--input-file", str(src)])
        assert rc_d == 0, err_d
        det = json.loads(out_d)
        assert det["match_count"] > 0

        rc_r, out_r, err_r = _run([
            "rewrite", "--patterns", str(PATTERNS), "--input-file", str(src), "--apply", "--output-file", str(out_file)
        ])
        assert rc_r == 0, err_r
        rew = json.loads(out_r)
        assert rew["applied"] is True
        assert out_file.exists()

        rc_s, out_s, err_s = _run(["score", "--patterns", str(PATTERNS), "--input-file", str(out_file)])
        assert rc_s == 0, err_s
        scored = json.loads(out_s)
        assert scored["score"] <= 0.000001


if __name__ == "__main__":
    test_detect_finds_matches_deterministically()
    test_rewrite_supports_empty_replacement_deterministically()
    test_score_is_stable()
    test_schema_validation_rejects_bad_jsonl_lines()
    test_e2e_detect_rewrite_score_apply()
    print("test_phase15_3_pattern_killer: all ok")
