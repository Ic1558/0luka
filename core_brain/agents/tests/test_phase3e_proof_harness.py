from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_phase3e_proof_harness_black_box() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "core_brain/agents/tests/run_phase3e_proof.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--json"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload["phase_id"] == "PHASE_3E"
    evidence = repo_root / payload["evidence_path"]
    assert evidence.exists()
    proof = json.loads(evidence.read_text(encoding="utf-8"))
    assert proof["ok"] is True
