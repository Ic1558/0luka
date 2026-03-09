#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.build_merkle_root import _canonical_json

EXPORT_VERSION = 1
REQUIRED_LOG_FILES = (
    "ledger_root.json",
    "segment_chain.jsonl",
    "epoch_manifest.jsonl",
    "rotation_registry.jsonl",
    "rotation_seals.jsonl",
)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _runtime_root(raw: str | None = None) -> Path:
    value = (raw or os.environ.get("LUKA_RUNTIME_ROOT", "")).strip()
    if not value:
        raise RuntimeError("runtime_root_missing")
    return Path(value).expanduser().resolve()


def _logs_dir(runtime_root: Path) -> Path:
    return runtime_root / "logs"


def _exports_dir(runtime_root: Path) -> Path:
    return runtime_root / "exports"


def _default_out_dir(runtime_root: Path) -> Path:
    return _exports_dir(runtime_root) / f"ledger_proof_{_utc_compact()}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_required_runtime_files(logs_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for name in REQUIRED_LOG_FILES:
        path = logs_dir / name
        if not path.exists():
            raise RuntimeError(f"missing_runtime_artifact:{path}")
        if not path.is_file():
            raise RuntimeError(f"runtime_artifact_not_file:{path}")
        paths.append(path)
    return paths


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return payload


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _build_export_manifest(
    *,
    runtime_root: Path,
    exported_files: list[Path],
    out_dir: Path,
) -> dict[str, Any]:
    ledger_root = _read_json(out_dir / "logs" / "ledger_root.json")
    epoch_anchor = ledger_root.get("epoch_anchor")
    if not isinstance(epoch_anchor, dict):
        raise RuntimeError("invalid_exported_epoch_anchor")

    source_files: list[dict[str, Any]] = []
    for src in exported_files:
        exported = out_dir / "logs" / src.name
        source_files.append(
            {
                "source": str(src),
                "exported": str(exported.relative_to(out_dir)),
                "size_bytes": exported.stat().st_size,
                "sha256": _sha256_file(exported),
            }
        )

    return {
        "version": EXPORT_VERSION,
        "ts_utc": _utc_now(),
        "runtime_root": str(runtime_root),
        "source_files": source_files,
        "ledger_root": {
            "merkle_root": ledger_root.get("merkle_root"),
            "segment_chain_head": ledger_root.get("segment_chain_head"),
        },
        "epoch_anchor": epoch_anchor,
        "segment_seq_min": ledger_root.get("segment_seq_min"),
        "segment_seq_max": ledger_root.get("segment_seq_max"),
        "file_count": len(source_files) + 2,
    }


def _write_checksums(out_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    targets = sorted(
        [
            path
            for path in out_dir.rglob("*")
            if path.is_file() and path.name != "checksums.sha256"
        ],
        key=lambda item: str(item.relative_to(out_dir)),
    )
    lines: list[str] = []
    for path in targets:
        rel = str(path.relative_to(out_dir))
        sha = _sha256_file(path)
        rows.append({"path": rel, "sha256": sha})
        lines.append(f"{sha}  {rel}")
    _write_text(out_dir / "checksums.sha256", "\n".join(lines) + "\n")
    return rows


def export_proof_pack(runtime_root: Path, out_dir: Path, *, dry_run: bool) -> dict[str, Any]:
    logs_dir = _logs_dir(runtime_root)
    source_files = _load_required_runtime_files(logs_dir)

    if not dry_run:
        if out_dir.exists():
            raise RuntimeError(f"export_dir_exists:{out_dir}")
        (out_dir / "logs").mkdir(parents=True, exist_ok=False)
        try:
            for src in source_files:
                shutil.copy2(src, out_dir / "logs" / src.name)

            manifest = _build_export_manifest(runtime_root=runtime_root, exported_files=source_files, out_dir=out_dir)
            _write_text(out_dir / "export_manifest.json", _canonical_json(manifest) + "\n")
            checksums = _write_checksums(out_dir)
        except Exception:
            shutil.rmtree(out_dir, ignore_errors=True)
            raise
    else:
        manifest = {
            "version": EXPORT_VERSION,
            "ts_utc": _utc_now(),
            "runtime_root": str(runtime_root),
            "source_files": [
                {
                    "source": str(src),
                    "exported": f"logs/{src.name}",
                    "size_bytes": src.stat().st_size,
                    "sha256": _sha256_file(src),
                }
                for src in source_files
            ],
        }
        ledger_root = _read_json(logs_dir / "ledger_root.json")
        epoch_anchor = ledger_root.get("epoch_anchor")
        manifest["ledger_root"] = {
            "merkle_root": ledger_root.get("merkle_root"),
            "segment_chain_head": ledger_root.get("segment_chain_head"),
        }
        manifest["epoch_anchor"] = epoch_anchor
        manifest["segment_seq_min"] = ledger_root.get("segment_seq_min")
        manifest["segment_seq_max"] = ledger_root.get("segment_seq_max")
        manifest["file_count"] = len(source_files) + 2
        checksums = []

    return {
        "ok": True,
        "dry_run": dry_run,
        "path": str(out_dir),
        "manifest": manifest,
        "checksums": checksums,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a self-contained ledger proof pack.")
    parser.add_argument("--runtime-root", help="Override runtime root")
    parser.add_argument("--out-dir", type=Path, help="Override export directory")
    parser.add_argument("--dry-run", action="store_true", help="Compute export metadata without writing files")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root(args.runtime_root)
        out_dir = args.out_dir.expanduser().resolve() if args.out_dir else _default_out_dir(runtime_root)
        result = export_proof_pack(runtime_root, out_dir, dry_run=args.dry_run)
    except RuntimeError as exc:
        error = str(exc)
        if error.startswith(("missing_runtime_artifact:", "runtime_artifact_not_file:", "runtime_root_missing", "invalid_json:", "json_not_object:")):
            rc = 2
        elif error.startswith(("invalid_exported_epoch_anchor",)):
            rc = 3
        elif error.startswith(("export_dir_exists:",)):
            rc = 4
        else:
            rc = 3
        payload = {"ok": False, "error": error, "exit_code": rc}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"export_ledger_proof_error:{error}", file=sys.stderr)
        return rc
    except Exception as exc:
        payload = {"ok": False, "error": f"export_write_failed:{exc}", "exit_code": 4}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"export_ledger_proof_error:export_write_failed:{exc}", file=sys.stderr)
        return 4

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"export_ledger_proof:ok path={result['path']} dry_run={result['dry_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
