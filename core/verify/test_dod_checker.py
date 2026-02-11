#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _load_dod_checker(repo_root: Path):
    module_path = repo_root / "tools" / "ops" / "dod_checker.py"
    spec = importlib.util.spec_from_file_location("dod_checker", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load dod_checker module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["dod_checker"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _head_sha(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True).strip()


def _dod_text(phase_id: str, commit_sha: str) -> str:
    return (
        f"# DoD — {phase_id}\n\n"
        "## 0. Metadata (MANDATORY)\n"
        f"- **Phase / Task ID**: {phase_id}\n"
        "- **Owner (Actor)**: Codex\n"
        "- **Gate**: G1\n"
        "- **Related SOT Section**: §X\n"
        "- **Target Status**: DESIGNED\n"
        f"- **Commit SHA**: {commit_sha}\n"
        "- **Date**: 2026-02-12\n"
    )


def _set_env(repo_root: Path, docs_dod: Path, reports_dir: Path, activity_path: Path, phase_status_path: Path) -> dict:
    prev = {
        "DOD_ROOT": os.environ.get("DOD_ROOT"),
        "DOD_DOCS_DIR": os.environ.get("DOD_DOCS_DIR"),
        "DOD_REPORTS_DIR": os.environ.get("DOD_REPORTS_DIR"),
        "LUKA_ACTIVITY_FEED_JSONL": os.environ.get("LUKA_ACTIVITY_FEED_JSONL"),
        "DOD_PHASE_STATUS_PATH": os.environ.get("DOD_PHASE_STATUS_PATH"),
    }
    os.environ["DOD_ROOT"] = str(repo_root)
    os.environ["DOD_DOCS_DIR"] = str(docs_dod)
    os.environ["DOD_REPORTS_DIR"] = str(reports_dir)
    os.environ["LUKA_ACTIVITY_FEED_JSONL"] = str(activity_path)
    os.environ["DOD_PHASE_STATUS_PATH"] = str(phase_status_path)
    return prev


def _restore_env(prev: dict) -> None:
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _run_cli(repo_root: Path, args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/ops/dod_checker.py", *args],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        env=env,
    )


def _mk_env(repo_root: Path, docs: Path, reports: Path, activity: Path, status: Path) -> dict:
    env = os.environ.copy()
    env["DOD_ROOT"] = str(repo_root)
    env["DOD_DOCS_DIR"] = str(docs)
    env["DOD_REPORTS_DIR"] = str(reports)
    env["LUKA_ACTIVITY_FEED_JSONL"] = str(activity)
    env["DOD_PHASE_STATUS_PATH"] = str(status)
    return env


def test_designed_no_activity_with_reachable_commit() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_MOCK.md", _dod_text("PHASE_MOCK", commit_sha))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_MOCK:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_MOCK", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "DESIGNED", out
    assert "activity.started" in out["missing"], out


def test_unreachable_commit_sha_is_partial() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_BADSHA.md", _dod_text("PHASE_BADSHA", "0000000"))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_BADSHA:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_BADSHA", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert "metadata.commit_sha_unreachable" in out["missing"], out


def test_partial_missing_verified() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_MOCK.md", _dod_text("PHASE_MOCK", commit_sha))
        _write_jsonl(
            activity,
            [
                {"phase_id": "PHASE_MOCK", "action": "started", "ts": "2026-02-12T00:00:00Z"},
                {"phase_id": "PHASE_MOCK", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
            ],
        )
        _write(phase_status, "phases:\n  PHASE_MOCK:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_MOCK", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert "activity.verified" in out["missing"], out


def test_partial_out_of_order_chain() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_MOCK.md", _dod_text("PHASE_MOCK", commit_sha))
        _write_jsonl(
            activity,
            [
                {"phase_id": "PHASE_MOCK", "action": "started", "ts": "2026-02-12T00:00:00Z"},
                {"phase_id": "PHASE_MOCK", "action": "verified", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_MOCK", "action": "completed", "ts": "2026-02-12T00:00:02Z"},
            ],
        )
        _write(phase_status, "phases:\n  PHASE_MOCK:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_MOCK", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert "activity.order_invalid" in out["missing"], out


def test_partial_evidence_path_missing() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_MOCK.md", _dod_text("PHASE_MOCK", commit_sha))
        _write_jsonl(
            activity,
            [
                {
                    "phase_id": "PHASE_MOCK",
                    "action": "started",
                    "ts": "2026-02-12T00:00:00Z",
                    "evidence": ["observability/proofs/missing.log"],
                },
                {"phase_id": "PHASE_MOCK", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_MOCK", "action": "verified", "ts": "2026-02-12T00:00:02Z"},
            ],
        )
        _write(phase_status, "phases:\n  PHASE_MOCK:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_MOCK", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert any(x.startswith("evidence.path_missing:") for x in out["missing"]), out


def test_partial_evidence_path_traversal_rejected() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_TRAV.md", _dod_text("PHASE_TRAV", commit_sha))
        _write_jsonl(
            activity,
            [
                {
                    "phase_id": "PHASE_TRAV",
                    "action": "started",
                    "ts": "2026-02-12T00:00:00Z",
                    "evidence": ["../secrets.txt"],
                },
                {"phase_id": "PHASE_TRAV", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_TRAV", "action": "verified", "ts": "2026-02-12T00:00:02Z"},
            ],
        )
        _write(phase_status, "phases:\n  PHASE_TRAV:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_TRAV", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert "evidence.path_traversal:../secrets.txt" in out["missing"], out


def test_gate_blocks_proven_when_prereq_not_proven() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_X.md", _dod_text("PHASE_X", commit_sha))
        _write_jsonl(
            activity,
            [
                {"phase_id": "PHASE_X", "action": "started", "ts": "2026-02-12T00:00:00Z"},
                {"phase_id": "PHASE_X", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase_id": "PHASE_X", "action": "verified", "ts": "2026-02-12T00:00:02Z"},
            ],
        )
        _write(
            phase_status,
            (
                "phases:\n"
                "  PHASE_2:\n"
                "    verdict: CLAIMED\n"
                "    requires:\n"
                "  PHASE_X:\n"
                "    verdict: DESIGNED\n"
                "    requires:\n"
                "      - PHASE_2\n"
            ),
        )

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_X", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PARTIAL", out
    assert "gate.requires_not_proven:PHASE_2" in out["missing"], out


def test_phase_id_and_phase_key_compatibility() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        evidence_file = tmp / "observability" / "proofs" / "ok.log"
        _write(evidence_file, "ok\n")
        digest = subprocess.check_output([sys.executable, "-c", f"import hashlib, pathlib;print(hashlib.sha256(pathlib.Path(r'{evidence_file}').read_bytes()).hexdigest())"], text=True).strip()

        _write(docs / "DOD__PHASE_KEYS.md", _dod_text("PHASE_KEYS", commit_sha))
        _write_jsonl(
            activity,
            [
                {"phase": "PHASE_KEYS", "action": "started", "ts": "2026-02-12T00:00:00Z", "evidence": [str(evidence_file)]},
                {"phase": "PHASE_KEYS", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {"phase": "PHASE_KEYS", "action": "verified", "ts": "2026-02-12T00:00:02Z", "hashes": {str(evidence_file): f"sha256:{digest}"}},
            ],
        )
        _write(phase_status, "phases:\n  PHASE_KEYS:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_KEYS", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PROVEN", out


def test_phase_id_preferred_over_phase_key() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dc = _load_dod_checker(repo_root)
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        evidence_file = tmp / "proof.log"
        _write(evidence_file, "x\n")
        digest = subprocess.check_output(
            [sys.executable, "-c", f"import hashlib, pathlib;print(hashlib.sha256(pathlib.Path(r'{evidence_file}').read_bytes()).hexdigest())"],
            text=True,
        ).strip()

        _write(docs / "DOD__PHASE_PREF.md", _dod_text("PHASE_PREF", commit_sha))
        _write_jsonl(
            activity,
            [
                {
                    "phase_id": "PHASE_PREF",
                    "phase": "WRONG_PHASE",
                    "action": "started",
                    "ts": "2026-02-12T00:00:00Z",
                    "evidence": [str(evidence_file)],
                },
                {"phase_id": "PHASE_PREF", "phase": "WRONG_PHASE", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {
                    "phase_id": "PHASE_PREF",
                    "phase": "WRONG_PHASE",
                    "action": "verified",
                    "ts": "2026-02-12T00:00:02Z",
                    "hashes": {str(evidence_file): f"sha256:{digest}"},
                },
            ],
        )
        _write(phase_status, "phases:\n  PHASE_PREF:\n    verdict: DESIGNED\n    requires:\n")

        prev = _set_env(repo_root, docs, reports, activity, phase_status)
        try:
            out = dc.run_check("PHASE_PREF", dc.resolve_paths())
        finally:
            _restore_env(prev)

    assert out["verdict"] == "PROVEN", out


def test_proven_demo_fixture_exit_0() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"
        evidence_file = tmp / "observability" / "proofs" / "log.jsonl"
        _write(evidence_file, "{\"ok\":true}\n")
        digest = subprocess.check_output([sys.executable, "-c", f"import hashlib, pathlib;print(hashlib.sha256(pathlib.Path(r'{evidence_file}').read_bytes()).hexdigest())"], text=True).strip()

        _write(docs / "DOD__PHASE_DEMO_PROVEN.md", _dod_text("PHASE_DEMO_PROVEN", commit_sha))
        _write_jsonl(
            activity,
            [
                {
                    "phase_id": "PHASE_DEMO_PROVEN",
                    "action": "started",
                    "ts": "2026-02-12T00:00:00Z",
                    "evidence": [str(evidence_file)],
                },
                {"phase_id": "PHASE_DEMO_PROVEN", "action": "completed", "ts": "2026-02-12T00:00:01Z"},
                {
                    "phase_id": "PHASE_DEMO_PROVEN",
                    "action": "verified",
                    "ts": "2026-02-12T00:00:02Z",
                    "hashes": {str(evidence_file): f"sha256:{digest}"},
                },
            ],
        )
        _write(phase_status, "phases:\n  PHASE_DEMO_PROVEN:\n    verdict: DESIGNED\n    requires:\n")
        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        proc = _run_cli(repo_root, ["--phase", "PHASE_DEMO_PROVEN"], env)

    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "PHASE_DEMO_PROVEN" in proc.stdout and "PROVEN" in proc.stdout, proc.stdout


def test_exit_code_designed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_D.md", _dod_text("PHASE_D", commit_sha))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_D:\n    verdict: DESIGNED\n    requires:\n")
        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        proc = _run_cli(repo_root, ["--phase", "PHASE_D"], env)

    assert proc.returncode == 3, proc.stdout + "\n" + proc.stderr


def test_exit_code_partial() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports = tmp / "observability" / "reports" / "dod_checker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_P.md", _dod_text("PHASE_P", commit_sha))
        _write_jsonl(activity, [{"phase_id": "PHASE_P", "action": "started", "ts": "2026-02-12T00:00:00Z"}])
        _write(phase_status, "phases:\n  PHASE_P:\n    verdict: DESIGNED\n    requires:\n")
        env = _mk_env(repo_root, docs, reports, activity, phase_status)
        proc = _run_cli(repo_root, ["--phase", "PHASE_P"], env)

    assert proc.returncode == 2, proc.stdout + "\n" + proc.stderr


def test_exit_code_internal_error() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    commit_sha = _head_sha(repo_root)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        docs = tmp / "docs" / "dod"
        reports_file = tmp / "observability" / "reports" / "dod_checker_blocker"
        activity = tmp / "observability" / "logs" / "activity.jsonl"
        phase_status = tmp / "core" / "governance" / "phase_status.yaml"

        _write(docs / "DOD__PHASE_E.md", _dod_text("PHASE_E", commit_sha))
        _write_jsonl(activity, [])
        _write(phase_status, "phases:\n  PHASE_E:\n    verdict: DESIGNED\n    requires:\n")
        _write(reports_file, "block")
        env = _mk_env(repo_root, docs, reports_file, activity, phase_status)
        proc = _run_cli(repo_root, ["--phase", "PHASE_E"], env)

    assert proc.returncode == 4, proc.stdout + "\n" + proc.stderr


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    test_designed_no_activity_with_reachable_commit()
    test_unreachable_commit_sha_is_partial()
    test_partial_missing_verified()
    test_partial_out_of_order_chain()
    test_partial_evidence_path_missing()
    test_partial_evidence_path_traversal_rejected()
    test_gate_blocks_proven_when_prereq_not_proven()
    test_phase_id_and_phase_key_compatibility()
    test_phase_id_preferred_over_phase_key()
    test_proven_demo_fixture_exit_0()
    test_exit_code_designed()
    test_exit_code_partial()
    test_exit_code_internal_error()
    print("test_dod_checker: all ok")
