from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import proof_bundle_builder


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_sources(repo_root: Path, runtime_root: Path) -> None:
    _write(repo_root / "observability" / "logs" / "activity_feed.jsonl", '{"action":"event"}\n')
    _write(runtime_root / "state" / "remediation_history.jsonl", '{"decision":"noop"}\n')
    _write(runtime_root / "state" / "approval_log.jsonl", '{"action":"approve"}\n')


def test_bundle_directory_created(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    _seed_sources(repo_root, runtime_root)
    monkeypatch.setattr(proof_bundle_builder, "_autonomy_policy_snapshot", lambda repo_root, runtime_root: "{}\n")
    monkeypatch.setattr(proof_bundle_builder, "_health_snapshot", lambda repo_root, runtime_root: "{}\n")

    payload = proof_bundle_builder.build_bundle(
        repo_root=repo_root,
        runtime_root=runtime_root,
        timestamp="20260308T120000Z",
    )

    bundle_dir = Path(payload["bundle_dir"])
    assert payload["ok"] is True
    assert bundle_dir.exists()
    assert bundle_dir.name == "bundle_20260308T120000Z"


def test_all_expected_files_present(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    _seed_sources(repo_root, runtime_root)
    monkeypatch.setattr(proof_bundle_builder, "_autonomy_policy_snapshot", lambda repo_root, runtime_root: '{"ok":true}\n')
    monkeypatch.setattr(proof_bundle_builder, "_health_snapshot", lambda repo_root, runtime_root: '{"status":"HEALTHY"}\n')

    payload = proof_bundle_builder.build_bundle(
        repo_root=repo_root,
        runtime_root=runtime_root,
        timestamp="20260308T120001Z",
    )

    assert sorted(payload["files"]) == sorted(
        [
            "activity_feed.jsonl",
            "approval_log.jsonl",
            "autonomy_policy.json",
            "hashes.sha256",
            "health_snapshot.json",
            "remediation_history.jsonl",
        ]
    )


def test_sha256_file_contains_valid_hashes(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    _seed_sources(repo_root, runtime_root)
    monkeypatch.setattr(proof_bundle_builder, "_autonomy_policy_snapshot", lambda repo_root, runtime_root: '{}\n')
    monkeypatch.setattr(proof_bundle_builder, "_health_snapshot", lambda repo_root, runtime_root: '{}\n')

    payload = proof_bundle_builder.build_bundle(
        repo_root=repo_root,
        runtime_root=runtime_root,
        timestamp="20260308T120002Z",
    )

    bundle_dir = Path(payload["bundle_dir"])
    hashes_lines = (bundle_dir / "hashes.sha256").read_text(encoding="utf-8").strip().splitlines()
    assert hashes_lines
    for line in hashes_lines:
        digest, filename = line.split("  ", 1)
        fpath = bundle_dir / filename
        expected = hashlib.sha256(fpath.read_bytes()).hexdigest()
        assert digest == expected


def test_bundle_generation_does_not_mutate_source_files(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    _seed_sources(repo_root, runtime_root)
    monkeypatch.setattr(proof_bundle_builder, "_autonomy_policy_snapshot", lambda repo_root, runtime_root: '{}\n')
    monkeypatch.setattr(proof_bundle_builder, "_health_snapshot", lambda repo_root, runtime_root: '{}\n')

    source_paths = [
        repo_root / "observability" / "logs" / "activity_feed.jsonl",
        runtime_root / "state" / "remediation_history.jsonl",
        runtime_root / "state" / "approval_log.jsonl",
    ]
    before = {str(p): p.read_text(encoding="utf-8") for p in source_paths}

    proof_bundle_builder.build_bundle(
        repo_root=repo_root,
        runtime_root=runtime_root,
        timestamp="20260308T120003Z",
    )

    after = {str(p): p.read_text(encoding="utf-8") for p in source_paths}
    assert before == after
