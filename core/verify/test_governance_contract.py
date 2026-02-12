from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    assert isinstance(payload, dict), f"Invalid YAML object in {path}"
    return payload


def test_core_never_imports_core_brain():
    violations: List[str] = []
    for py_file in sorted((ROOT / "core").rglob("*.py")):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\bfrom\s+core_brain\b", content) or re.search(r"\bimport\s+core_brain\b", content):
            violations.append(str(py_file.relative_to(ROOT)))
    assert not violations, f"Core imports core_brain in: {violations}"


def test_no_hard_paths_in_governance():
    violations: List[str] = []
    for path in sorted((ROOT / "core/governance").rglob("*")):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "/" + "Users/" in content:
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Hard-coded " + "/" + "Users/ paths found in: {violations}"


def test_governance_lock_manifest_consistent():
    manifest_path = ROOT / "core/governance/governance_lock_manifest.json"
    assert manifest_path.exists(), "governance_lock_manifest.json missing"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload.get("algorithm") == "sha256"
    files = payload.get("files")
    assert isinstance(files, list) and files, "manifest files[] missing/empty"
    for item in files:
        assert isinstance(item, dict), f"invalid manifest entry: {item!r}"
        rel = str(item.get("path", "")).strip()
        expected = str(item.get("sha256", "")).strip().lower()
        assert rel and expected, f"incomplete manifest entry: {item!r}"
        target = ROOT / rel
        assert target.exists(), f"manifest path missing: {rel}"
        actual = _sha256_file(target)
        assert actual == expected, f"hash mismatch for {rel}"


def test_no_stale_copies():
    sop = _load_yaml(ROOT / "core/governance/separation_of_powers.yaml")
    for entry in sop.get("canonical_sources", []):
        if not isinstance(entry, dict) or "no_copy_in" not in entry:
            continue
        spec = str(entry.get("spec", "")).strip()
        no_copy_in = str(entry.get("no_copy_in", "")).strip()
        assert spec and no_copy_in, f"invalid canonical_sources entry: {entry}"
        stale = ROOT / no_copy_in / Path(spec).name
        assert not stale.exists(), f"stale copy detected: {stale.relative_to(ROOT)}"


def test_derived_files_declare_source():
    sop = _load_yaml(ROOT / "core/governance/separation_of_powers.yaml")
    for entry in sop.get("canonical_sources", []):
        if not isinstance(entry, dict) or "derived" not in entry:
            continue
        spec = str(entry.get("spec", "")).strip()
        derived = str(entry.get("derived", "")).strip()
        assert spec and derived, f"invalid derived entry: {entry}"
        derived_path = ROOT / derived
        assert derived_path.exists(), f"missing derived file: {derived}"
        head = "\n".join(derived_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:12])
        assert f"# derived_from: {spec}" in head, f"derived header missing in {derived}"


def test_cross_repo_manifest_no_hard_paths():
    manifest = _load_yaml(ROOT / "core/governance/cross_repo_manifest.yaml")
    repos = manifest.get("repos", [])
    assert isinstance(repos, list) and repos, "cross-repo manifest repos missing"
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        local_path = repo.get("local_path")
        if local_path:
            local_path = str(local_path)
            assert not local_path.startswith("/"), f"hard absolute path found: {local_path}"
            assert "/" + "Users/" not in local_path, f"forbidden hard path found: {local_path}"


def test_abi_frozen():
    abi = _load_yaml(ROOT / "core/governance/tier3_abi.yaml")
    assert abi.get("frozen") is True, "ABI must remain frozen"
    assert abi.get("ABI_version") == "3.0.0", "ABI_version must remain 3.0.0"


def test_ring_classification():
    sop = _load_yaml(ROOT / "core/governance/separation_of_powers.yaml")
    rings = sop.get("rings")
    assert isinstance(rings, dict), "rings missing"
    for ring in ("R3", "R2", "R1", "R0"):
        assert ring in rings, f"{ring} missing from rings"
        row = rings[ring]
        assert isinstance(row, dict), f"{ring} must be map"
        for field in ("name", "paths", "role", "import_rule", "change_control"):
            assert field in row, f"{field} missing in {ring}"
        assert isinstance(row.get("paths"), list) and row["paths"], f"{ring}.paths must be non-empty list"
