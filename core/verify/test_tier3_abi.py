from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _checker_path() -> Path:
    return _repo_root() / "tools/ops/dod_checker.py"


def _head_sha(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        text=True,
    ).strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _dod_text(phase_id: str, commit_sha: str) -> str:
    return (
        f"- **Phase / Task ID**: {phase_id}\n"
        f"- **Commit SHA**: {commit_sha}\n"
        "- **Gate**: G1\n"
        "- **Related SOT Section**: §Tier3.ABI\n"
    )


def _mk_env(repo_root: Path, docs: Path, reports: Path, activity: Path, phase_status: Path) -> Dict[str, str]:
    env = os.environ.copy()
    env["DOD_ROOT"] = str(repo_root)
    env["DOD_DOCS_DIR"] = str(docs)
    env["DOD_REPORTS_DIR"] = str(reports)
    env["LUKA_ACTIVITY_FEED_JSONL"] = str(activity)
    env["DOD_PHASE_STATUS_PATH"] = str(phase_status)
    return env


def _run_cli(args, env: Dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_checker_path()), *args],
        cwd=str(_repo_root()),
        env=env,
        text=True,
        capture_output=True,
    )


def test_abi_file_loads() -> None:
    abi_path = _repo_root() / "core/governance/tier3_abi.yaml"
    contract = json.loads(abi_path.read_text(encoding="utf-8"))
    assert contract["ABI_version"] == "3.0.0"
    assert contract["frozen"] is True


def test_exit_code_semantics_preserved() -> None:
    repo_root = _repo_root()
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        evidence = tmp / "proof.log"
        _write(evidence, "ok\n")

        def _run_case(event_rows: List[Dict[str, str]], expected_exit: int) -> None:
            _write(docs / "DOD__PHASE_ONE.md", _dod_text("PHASE_ONE", commit_sha))
            _write_jsonl(activity, event_rows)
            _write(phase_status, "phases:\n  PHASE_ONE:\n    verdict: DESIGNED\n    requires:\n")
            env = _mk_env(repo_root, docs, reports, activity, phase_status)
            proc = _run_cli(["--all", "--json"], env)
            assert proc.returncode == expected_exit, proc.stdout + "\n" + proc.stderr

        _run_case(
            [
                {"phase_id": "PHASE_ONE", "action": "started", "ts": "2026-02-12T00:00:00Z", "evidence": [str(evidence)]},
                {"phase_id": "PHASE_ONE", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_ONE", "action": "verified", "ts": "2026-02-12T00:00:02Z"},
            ],
            0,
        )
        _run_case(
            [
                {"phase_id": "PHASE_ONE", "action": "started", "ts": "2026-02-12T00:00:00Z", "evidence": [str(evidence)]},
            ],
            2,
        )
        _run_case([], 3)


def test_invalid_verdict_name_triggers_failure() -> None:
    repo_root = _repo_root()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        abi_file = tmp / "abi_invalid_verdict.yaml"

        _write(docs / "DOD__PHASE_ONE.md", _dod_text("PHASE_ONE", _head_sha(repo_root)))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_ONE:\n    verdict: DESIGNED\n    requires:\n")
        _write(
            abi_file,
            json.dumps(
                {
                    "ABI_version": "3.0.0",
                    "frozen": True,
                    "exit_code_contract": {
                        "0": "all non-fixture phases PROVEN",
                        "3": "missing proof",
                        "4": "registry/schema error",
                    },
                    "valid_verdicts": ["DESIGNED", "BROKEN", "PROVEN"],
                    "proof_requirements": [
                        "reachable commit_sha (40 hex)",
                        "activity chain: started -> completed -> verified",
                        "taxonomy_ok = true",
                        "synthetic_detected = false",
                        "evidence_path must exist and be readable",
                    ],
                    "fixture_rule": ["excluded in --all", "included in explicit --phase"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        env["DOD_TIER3_ABI_PATH"] = str(abi_file)
        proc = _run_cli(["--all", "--json"], env)
        assert proc.returncode == 4, proc.stdout + "\n" + proc.stderr
        assert "tier3_abi_invalid_valid_verdicts" in (proc.stdout + proc.stderr)


def test_missing_proof_requirement_triggers_failure() -> None:
    repo_root = _repo_root()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        abi_file = tmp / "abi_missing_req.yaml"

        _write(docs / "DOD__PHASE_ONE.md", _dod_text("PHASE_ONE", _head_sha(repo_root)))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_ONE:\n    verdict: DESIGNED\n    requires:\n")
        _write(
            abi_file,
            json.dumps(
                {
                    "ABI_version": "3.0.0",
                    "frozen": True,
                    "exit_code_contract": {
                        "0": "all non-fixture phases PROVEN",
                        "3": "missing proof",
                        "4": "registry/schema error",
                    },
                    "valid_verdicts": ["DESIGNED", "PARTIAL", "PROVEN"],
                    "proof_requirements": [
                        "reachable commit_sha (40 hex)",
                        "activity chain: started -> completed -> verified",
                        "taxonomy_ok = true",
                        "synthetic_detected = false",
                    ],
                    "fixture_rule": ["excluded in --all", "included in explicit --phase"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        env["DOD_TIER3_ABI_PATH"] = str(abi_file)
        proc = _run_cli(["--all", "--json"], env)
        assert proc.returncode == 4, proc.stdout + "\n" + proc.stderr
        assert "tier3_abi_missing_proof_requirement" in (proc.stdout + proc.stderr)


def test_fixture_exclusion_still_works() -> None:
    repo_root = _repo_root()
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        evidence = tmp / "proof.log"
        _write(evidence, "ok\n")

        _write(docs / "DOD__PHASE_REAL.md", _dod_text("PHASE_REAL", commit_sha))
        _write(docs / "DOD__PHASE_FIX.md", _dod_text("PHASE_FIX", commit_sha))
        _write_jsonl(
            activity,
            [
                {"phase_id": "PHASE_REAL", "action": "started", "ts": "2026-02-12T00:00:00Z", "evidence": [str(evidence)]},
                {"phase_id": "PHASE_REAL", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_REAL", "action": "verified", "ts": "2026-02-12T00:00:02Z"},
            ],
        )
        _write(
            phase_status,
            (
                "phases:\n"
                "  PHASE_REAL:\n"
                "    verdict: DESIGNED\n"
                "    requires:\n"
                "  PHASE_FIX:\n"
                "    verdict: DESIGNED\n"
                "    requires:\n"
                "    kind: fixture\n"
            ),
        )

        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        proc = _run_cli(["--all", "--json"], env)
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
        payload = json.loads(proc.stdout)
        by_phase = {item["phase_id"]: item for item in payload["results"]}
        assert by_phase["PHASE_REAL"]["verdict"] == "PROVEN"
        assert by_phase["PHASE_FIX"]["verdict"] == "DESIGNED"
