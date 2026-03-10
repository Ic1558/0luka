#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_REPO_ROOT = Path("/Users/icmini/0luka")
CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _bundle_dir(repo_root: Path, stamp: str) -> Path:
    return repo_root / "observability" / "proof_bundle" / f"bundle_{stamp}"


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _write_text(dst: Path, text: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def _resolve_required_sources(repo_root: Path, runtime_root: Path) -> dict[str, Path]:
    approval_primary = runtime_root / "state" / "approval_log.jsonl"
    approval_fallback = runtime_root / "state" / "approval_actions.jsonl"
    remediation_primary = runtime_root / "state" / "remediation_history.jsonl"
    remediation_fallback = runtime_root / "state" / "remediation_actions.jsonl"

    activity = CANONICAL_REPO_ROOT / "observability" / "logs" / "activity_feed.jsonl"
    if not activity.exists():
        activity = repo_root / "observability" / "logs" / "activity_feed.jsonl"

    sources: dict[str, Path] = {
        "activity_feed.jsonl": activity,
        "remediation_history.jsonl": remediation_primary if remediation_primary.exists() else remediation_fallback,
        "approval_log.jsonl": approval_primary if approval_primary.exists() else approval_fallback,
    }

    missing = [name for name, path in sources.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"missing_source_files:{','.join(sorted(missing))}")
    return sources


def _autonomy_policy_snapshot(repo_root: Path, runtime_root: Path) -> str:
    policy_path = repo_root / "core" / "policy" / "autonomy_policy.json"
    if policy_path.exists():
        return policy_path.read_text(encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "tools/ops/autonomy_policy.py", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LUKA_RUNTIME_ROOT": str(runtime_root)},
    )
    stream = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0 or not stream:
        raise RuntimeError("autonomy_policy_snapshot_failed")
    payload = json.loads(stream)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _health_snapshot(repo_root: Path, runtime_root: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "core/health.py", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LUKA_RUNTIME_ROOT": str(runtime_root)},
    )
    stream = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0 or not stream:
        raise RuntimeError("health_snapshot_failed")
    payload = json.loads(stream)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_hashes(bundle_path: Path) -> Path:
    lines: list[str] = []
    for path in sorted(bundle_path.glob("*")):
        if not path.is_file() or path.name == "hashes.sha256":
            continue
        lines.append(f"{_sha256(path)}  {path.name}")
    hashes_path = bundle_path / "hashes.sha256"
    _write_text(hashes_path, "\n".join(lines) + "\n")
    return hashes_path


def build_bundle(*, repo_root: Path | None = None, runtime_root: Path | None = None, timestamp: str | None = None) -> dict[str, object]:
    resolved_repo_root = (repo_root or _repo_root()).resolve()
    resolved_runtime_root = (runtime_root or _runtime_root()).resolve()
    stamp = timestamp or _timestamp()
    bundle_path = _bundle_dir(resolved_repo_root, stamp)
    bundle_path.mkdir(parents=True, exist_ok=False)

    sources = _resolve_required_sources(resolved_repo_root, resolved_runtime_root)
    for target_name, src in sources.items():
        _copy_file(src, bundle_path / target_name)

    _write_text(bundle_path / "autonomy_policy.json", _autonomy_policy_snapshot(resolved_repo_root, resolved_runtime_root))
    _write_text(bundle_path / "health_snapshot.json", _health_snapshot(resolved_repo_root, resolved_runtime_root))
    hashes_path = _write_hashes(bundle_path)

    return {
        "ok": True,
        "bundle_dir": str(bundle_path),
        "timestamp": stamp,
        "files": sorted([p.name for p in bundle_path.iterdir() if p.is_file()]),
        "hashes_file": str(hashes_path),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic proof bundle for external verification")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument("--timestamp", type=str, default="", help="fixed UTC timestamp for deterministic tests")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        payload = build_bundle(timestamp=args.timestamp or None)
    except Exception as exc:
        payload = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 2

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
