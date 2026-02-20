"""
Constitutional Governance Enforcement Tests

Machine-enforced boundary tests for separation_of_powers.yaml.
"The test is the real governance. The markdown explains why."
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOP_PATH = ROOT / "core" / "governance" / "separation_of_powers.yaml"


def _load_sop():
    with open(SOP_PATH) as f:
        return yaml.safe_load(f)


def test_ring_classification():
    sop = _load_sop()
    assert "rings" in sop
    required_fields = {"name", "paths", "role", "import_rule", "change_control"}
    for ring_id in ("R3", "R2", "R1", "R0"):
        assert ring_id in sop["rings"], f"Missing ring: {ring_id}"
        ring = sop["rings"][ring_id]
        missing = required_fields - set(ring.keys())
        assert not missing, f"{ring_id} missing fields: {missing}"


def test_core_never_imports_core_brain():
    violations = []
    core_dir = ROOT / "core"
    for py_file in core_dir.rglob("*.py"):
        # Skip test files — they may cross-validate intentionally
        if "verify" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "from core_brain" in stripped or "import core_brain" in stripped:
                rel = py_file.relative_to(ROOT)
                violations.append(f"{rel}:{line_no}: {stripped}")
    assert not violations, (
        "Constitutional layer (core/) must not import from operational layer (core_brain/):\n"
        + "\n".join(violations)
    )


def test_no_hard_paths_in_governance():
    violations = []
    gov_dir = ROOT / "core" / "governance"
    for f in gov_dir.rglob("*"):
        if not f.is_file():
            continue
        # Skip decisions/ — historical R0 evidence, append-only
        if "decisions" in f.relative_to(gov_dir).parts:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            if "/Users/" in line:
                rel = f.relative_to(ROOT)
                violations.append(f"{rel}:{line_no}")
    assert not violations, (
        "No hard paths (/Users/) allowed in governance files:\n"
        + "\n".join(violations)
    )


def test_no_stale_copies():
    sop = _load_sop()
    stale = []
    for entry in sop.get("canonical_sources", []):
        no_copy_dir = entry.get("no_copy_in")
        if not no_copy_dir:
            continue
        spec_path = entry.get("spec", "")
        spec_name = Path(spec_path).name
        forbidden_path = ROOT / no_copy_dir / spec_name
        if forbidden_path.exists():
            stale.append(f"{no_copy_dir}{spec_name} (copy of {spec_path})")
    assert not stale, (
        "Stale copies found where no_copy_in is declared:\n"
        + "\n".join(stale)
    )


def test_derived_files_declare_source():
    sop = _load_sop()
    missing = []
    for entry in sop.get("canonical_sources", []):
        derived = entry.get("derived")
        spec = entry.get("spec")
        if not derived or not spec:
            continue
        derived_path = ROOT / derived
        if not derived_path.exists():
            missing.append(f"{derived} does not exist")
            continue
        content = derived_path.read_text(encoding="utf-8", errors="ignore")
        if "derived_from:" not in content and spec not in content:
            missing.append(f"{derived} does not reference source {spec}")
    assert not missing, (
        "Derived files must declare their source:\n"
        + "\n".join(missing)
    )


def test_cross_repo_manifest_no_hard_paths():
    manifest_path = ROOT / "core" / "governance" / "cross_repo_manifest.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    violations = []
    for repo in manifest.get("repos", []):
        local_path = repo.get("local_path", "")
        if local_path.startswith("/"):
            violations.append(f"repo '{repo.get('id')}': local_path={local_path}")
    assert not violations, (
        "Cross-repo manifest must not use absolute paths:\n"
        + "\n".join(violations)
    )


def test_abi_frozen():
    abi_path = ROOT / "core" / "governance" / "tier3_abi.yaml"
    contract = json.loads(abi_path.read_text(encoding="utf-8"))
    assert contract["frozen"] is True, "ABI must be frozen"
    assert contract["ABI_version"] == "3.0.0", f"ABI version must be 3.0.0, got {contract['ABI_version']}"


def test_governance_lock_manifest_consistent():
    from tools.ops.governance_file_lock import verify_manifest_payload

    manifest_path = ROOT / "core" / "governance" / "governance_lock_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = verify_manifest_payload(payload, ROOT)
    assert not errors, (
        "Governance lock manifest integrity errors:\n"
        + "\n".join(errors)
    )


def test_ontology_path_exists():
    ontology_path = ROOT / "core" / "governance" / "ontology.yaml"
    assert ontology_path.exists(), f"Canonical ontology missing: {ontology_path}"
    with open(ontology_path) as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "ontology.yaml must be valid YAML dict"
