#!/usr/bin/env python3
"""
Governance File Lock Guard

Step 2 goals:
- Hash-lock governance-critical files.
- Block critical mutations unless governance label is present.
- Require lock manifest refresh when critical files change.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


DEFAULT_CRITICAL_SPECS = (
    "core/governance/**",
    "docs/dod/**",
    "tools/ops/dod_checker.py",
    "phase_status.yaml",
    "core/governance/phase_status.yaml",
)
DEFAULT_MANIFEST_PATH = "core/governance/governance_lock_manifest.json"
DEFAULT_REQUIRED_LABEL = "governance-change"


@dataclass(frozen=True)
class MutationDecision:
    ok: bool
    critical_changed: List[str]
    errors: List[str]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_glob(spec: str) -> bool:
    return any(ch in spec for ch in "*?[]")


def _matches_spec(rel_path: str, spec: str) -> bool:
    if spec.endswith("/**"):
        prefix = spec[:-3].rstrip("/")
        return rel_path == prefix or rel_path.startswith(f"{prefix}/")
    if _is_glob(spec):
        return fnmatch.fnmatch(rel_path, spec)
    return rel_path == spec


def is_critical_path(rel_path: str, specs: Sequence[str]) -> bool:
    rel = rel_path.replace("\\", "/").strip()
    if not rel:
        return False
    return any(_matches_spec(rel, spec) for spec in specs)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_spec_files(root: Path, spec: str) -> Iterable[Path]:
    if spec.endswith("/**"):
        base = root / spec[:-3]
        if base.is_file():
            yield base
            return
        if not base.exists():
            return
        for path in base.rglob("*"):
            if path.is_file():
                yield path
        return

    if _is_glob(spec):
        for path in root.glob(spec):
            if path.is_file():
                yield path
        return

    direct = root / spec
    if direct.is_file():
        yield direct
        return
    if direct.is_dir():
        for path in direct.rglob("*"):
            if path.is_file():
                yield path


def collect_critical_files(root: Path, specs: Sequence[str], manifest_rel: str) -> List[str]:
    manifest_rel_norm = manifest_rel.replace("\\", "/")
    files: Set[str] = set()
    for spec in specs:
        for path in _iter_spec_files(root, spec):
            rel = path.relative_to(root).as_posix()
            if rel == manifest_rel_norm:
                continue
            files.add(rel)
    return sorted(files)


def build_manifest_payload(
    root: Path, specs: Sequence[str], manifest_rel: str, generated_at_utc: str | None = None
) -> Dict[str, Any]:
    files = collect_critical_files(root, specs, manifest_rel)
    entries = [{"path": rel, "sha256": _sha256(root / rel)} for rel in files]
    return {
        "generated_at_utc": generated_at_utc or _utc_now(),
        "algorithm": "sha256",
        "required_label": DEFAULT_REQUIRED_LABEL,
        "critical_specs": list(specs),
        "files": entries,
    }


def verify_manifest_payload(payload: Dict[str, Any], root: Path) -> List[str]:
    errors: List[str] = []
    files = payload.get("files")
    if not isinstance(files, list):
        return ["manifest malformed: files must be a list"]

    for item in files:
        if not isinstance(item, dict):
            errors.append("manifest malformed: file entry must be object")
            continue
        rel = str(item.get("path", "")).replace("\\", "/").strip()
        expected = str(item.get("sha256", "")).strip().lower()
        if not rel or not expected:
            errors.append(f"manifest malformed entry: {item}")
            continue
        file_path = root / rel
        if not file_path.exists():
            errors.append(f"missing: {rel}")
            continue
        actual = _sha256(file_path)
        if actual != expected:
            errors.append(f"hash mismatch: {rel}")
    return errors


def evaluate_mutation(
    changed_files: Sequence[str],
    deleted_files: Sequence[str],
    labels: Sequence[str],
    required_label: str,
    manifest_rel: str,
    specs: Sequence[str],
) -> MutationDecision:
    changed_norm = sorted({p.replace("\\", "/").strip() for p in changed_files if p.strip()})
    deleted_norm = sorted({p.replace("\\", "/").strip() for p in deleted_files if p.strip()})
    label_set = {str(x).strip() for x in labels if str(x).strip()}
    errors: List[str] = []

    critical_changed = [p for p in changed_norm if is_critical_path(p, specs)]
    critical_deleted = [p for p in deleted_norm if is_critical_path(p, specs)]

    if critical_changed:
        if required_label not in label_set:
            errors.append(
                f"critical files changed without '{required_label}' label: {', '.join(critical_changed)}"
            )
        manifest_norm = manifest_rel.replace("\\", "/")
        if manifest_norm not in changed_norm:
            errors.append(
                f"critical files changed but lock manifest not updated: {manifest_norm}"
            )

    if critical_deleted:
        errors.append(f"critical files deleted: {', '.join(critical_deleted)}")

    return MutationDecision(ok=not errors, critical_changed=critical_changed, errors=errors)


def _git_diff_name_only(root: Path, base: str, head: str) -> List[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", base, head],
        cwd=str(root),
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def _git_diff_deleted(root: Path, base: str, head: str) -> List[str]:
    out = subprocess.check_output(
        ["git", "diff", "--diff-filter=D", "--name-only", base, head],
        cwd=str(root),
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def _parse_labels(raw: str) -> List[str]:
    if not raw.strip():
        return []
    decoded = json.loads(raw)
    if not isinstance(decoded, list):
        raise ValueError("labels-json must decode to list")
    return [str(x) for x in decoded]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Governance file lock guard")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, help="Lock manifest path")
    parser.add_argument(
        "--critical-spec",
        action="append",
        dest="critical_specs",
        help="Override critical path/glob (repeatable). Defaults to built-in list.",
    )
    parser.add_argument("--build-manifest", action="store_true", help="Generate lock manifest")
    parser.add_argument("--verify-manifest", action="store_true", help="Verify lock manifest")
    parser.add_argument("--check-mutation", action="store_true", help="Enforce PR mutation policy")
    parser.add_argument("--base", help="Base git ref for mutation check")
    parser.add_argument("--head", help="Head git ref for mutation check")
    parser.add_argument("--labels-json", default="[]", help="PR labels JSON array")
    parser.add_argument("--required-label", default=DEFAULT_REQUIRED_LABEL, help="Required PR label")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)

    root = _repo_root()
    manifest_rel = args.manifest
    manifest_path = root / manifest_rel
    specs = tuple(args.critical_specs) if args.critical_specs else DEFAULT_CRITICAL_SPECS

    if not (args.build_manifest or args.verify_manifest or args.check_mutation):
        parser.error("specify at least one mode: --build-manifest / --verify-manifest / --check-mutation")

    report: Dict[str, Any] = {"ok": True, "errors": []}

    if args.build_manifest:
        payload = build_manifest_payload(root, specs, manifest_rel)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["manifest"] = manifest_rel
        report["file_count"] = len(payload["files"])

    if args.verify_manifest:
        if not manifest_path.exists():
            report["ok"] = False
            report["errors"].append(f"manifest missing: {manifest_rel}")
        else:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            errors = verify_manifest_payload(payload, root)
            if errors:
                report["ok"] = False
                report["errors"].extend(errors)
            report["verified_files"] = len(payload.get("files", []))

    if args.check_mutation:
        if not args.base or not args.head:
            parser.error("--check-mutation requires --base and --head")
        try:
            labels = _parse_labels(args.labels_json)
        except ValueError as exc:
            parser.error(str(exc))
        changed = _git_diff_name_only(root, args.base, args.head)
        deleted = _git_diff_deleted(root, args.base, args.head)
        decision = evaluate_mutation(
            changed_files=changed,
            deleted_files=deleted,
            labels=labels,
            required_label=args.required_label,
            manifest_rel=manifest_rel,
            specs=specs,
        )
        report["changed_files"] = len(changed)
        report["critical_changed"] = decision.critical_changed
        if not decision.ok:
            report["ok"] = False
            report["errors"].extend(decision.errors)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"governance_file_lock: {status}")
        for key in ("manifest", "file_count", "verified_files", "changed_files"):
            if key in report:
                print(f"{key}: {report[key]}")
        if report.get("critical_changed"):
            print("critical_changed:")
            for p in report["critical_changed"]:
                print(f"  - {p}")
        if report["errors"]:
            print("errors:")
            for err in report["errors"]:
                print(f"  - {err}")

    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
