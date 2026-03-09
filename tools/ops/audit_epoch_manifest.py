#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

GENESIS_PREV_EPOCH_HASH = "0000000000000000"


def _default_manifest_path() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime")).strip()
    return Path(runtime_root).expanduser() / "logs" / "epoch_manifest.jsonl"


def _compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    canonical = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_log_head_shape(head: Any) -> bool:
    if not isinstance(head, dict):
        return False
    # Runtime shape (live snapshots)
    if (
        isinstance(head.get("path"), str)
        and isinstance(head.get("exists"), bool)
        and isinstance(head.get("size_bytes"), int)
        and isinstance(head.get("tail_sha256"), str)
    ):
        return True
    # Fixture shape (CI synthetic anchors)
    if (
        isinstance(head.get("last_event_hash"), str)
        and isinstance(head.get("line_count"), int)
    ):
        return True
    return False


def _audit_epoch_manifest(path: Path, *, required_logs: list[str] | None = None) -> dict[str, Any]:
    required = required_logs[:] if required_logs else ["dispatcher"]
    required = [item for item in required if item]
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "epoch_lines": 0,
            "required_logs": required,
            "head_completeness_ok": False,
            "last_epoch_hash": None,
            "errors": [{"line": 0, "error": f"missing_file:{path}"}],
        }
    if not path.is_file():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "epoch_lines": 0,
            "required_logs": required,
            "head_completeness_ok": False,
            "last_epoch_hash": None,
            "errors": [{"line": 0, "error": f"not_a_file:{path}"}],
        }

    errors: list[dict[str, Any]] = []
    lines_total = 0
    epoch_lines = 0
    last_epoch_hash: str | None = None
    head_completeness_ok = True
    first_epoch_line: int | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            lines_total += 1
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_no, "error": "invalid_json", "detail": str(exc)})
                continue
            if not isinstance(entry, dict):
                errors.append({"line": line_no, "error": "non_object_json"})
                continue

            epoch_id = entry.get("epoch_id")
            prev_epoch_hash = entry.get("prev_epoch_hash")
            epoch_hash = entry.get("epoch_hash")
            log_heads = entry.get("log_heads")

            if not isinstance(epoch_id, int) or epoch_id < 1:
                errors.append({"line": line_no, "error": "invalid_epoch_id"})
                continue
            if not isinstance(prev_epoch_hash, str) or not prev_epoch_hash:
                errors.append({"line": line_no, "error": "invalid_prev_epoch_hash"})
                continue
            if not isinstance(epoch_hash, str) or not epoch_hash:
                errors.append({"line": line_no, "error": "invalid_epoch_hash"})
                continue
            if not isinstance(log_heads, dict):
                errors.append({"line": line_no, "error": "invalid_log_heads"})
                continue

            if first_epoch_line is None:
                first_epoch_line = line_no
                if prev_epoch_hash != GENESIS_PREV_EPOCH_HASH:
                    errors.append(
                        {
                            "line": line_no,
                            "error": "genesis_prev_epoch_hash_mismatch",
                            "expected": GENESIS_PREV_EPOCH_HASH,
                            "observed": prev_epoch_hash,
                        }
                    )
            else:
                if prev_epoch_hash != last_epoch_hash:
                    errors.append(
                        {
                            "line": line_no,
                            "error": "prev_epoch_hash_mismatch",
                            "expected": last_epoch_hash,
                            "observed": prev_epoch_hash,
                        }
                    )

            missing_logs = [log for log in required if log not in log_heads]
            if missing_logs:
                head_completeness_ok = False
                errors.append({"line": line_no, "error": "missing_registered_head", "missing": missing_logs})
            for log_name in required:
                if log_name not in log_heads:
                    continue
                if not _validate_log_head_shape(log_heads.get(log_name)):
                    head_completeness_ok = False
                    errors.append({"line": line_no, "error": "invalid_log_head_shape", "log": log_name})

            if "activity_feed" in log_heads:
                head_completeness_ok = False
                errors.append({"line": line_no, "error": "forbidden_log_head", "log": "activity_feed"})

            computed = _compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)
            if computed != epoch_hash:
                errors.append({"line": line_no, "error": "epoch_hash_mismatch", "computed": computed, "stored": epoch_hash})
                continue

            epoch_lines += 1
            last_epoch_hash = epoch_hash

    ok = len(errors) == 0
    return {
        "ok": ok,
        "path": str(path),
        "lines_total": lines_total,
        "epoch_lines": epoch_lines,
        "required_logs": required,
        "head_completeness_ok": head_completeness_ok,
        "first_epoch_line": first_epoch_line,
        "last_epoch_hash": last_epoch_hash,
        "errors": errors[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit epoch manifest hash chain and log-head completeness.")
    parser.add_argument("--path", type=Path, help="Path to epoch_manifest.jsonl")
    parser.add_argument("--manifest", type=Path, help="Alias for --path")
    parser.add_argument("--required-log", action="append", default=[], help="Required log head key (repeatable)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    path = args.manifest if args.manifest else (args.path if args.path else _default_manifest_path())
    required_logs = args.required_log if args.required_log else None
    report = _audit_epoch_manifest(path, required_logs=required_logs)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
