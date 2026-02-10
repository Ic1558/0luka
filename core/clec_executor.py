#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import hashlib
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
ALLOWED_CLEC_COMMANDS = [
    "pytest",
    "python3 -m pytest",
    "python3 core/verify/*.py",
    "git status",
    "git diff",
]


class CLECExecutorError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_join(path_str: str) -> Path:
    rel = Path(path_str)
    if rel.is_absolute() or ".." in rel.parts:
        raise CLECExecutorError(f"invalid_relative_path:{path_str}")
    full = (ROOT / rel).resolve(strict=False)
    if full != ROOT and ROOT not in full.parents:
        raise CLECExecutorError(f"path_outside_root:{path_str}")
    return full


def _command_allowed(command: str) -> bool:
    normalized = " ".join(shlex.split(command.strip()))
    if not normalized:
        return False
    for pattern in ALLOWED_CLEC_COMMANDS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def _run_verify_checks(verify: List[Dict[str, Any]]) -> None:
    for idx, check in enumerate(verify):
        name = check.get("check")
        target = check.get("target", "")
        if name == "gate.fs.exists":
            if not _safe_join(target).exists():
                raise CLECExecutorError(f"verify_failed:index={idx}:gate.fs.exists")
        elif name == "gate.hash.present":
            if not _safe_join(target).is_file():
                raise CLECExecutorError(f"verify_failed:index={idx}:gate.hash.present")
            _sha256(_safe_join(target))
        elif name == "gate.test.run":
            command = str(check.get("command", "")).strip()
            if not _command_allowed(command):
                raise CLECExecutorError(f"verify_command_not_allowed:index={idx}")
        else:
            raise CLECExecutorError(f"verify_check_unsupported:index={idx}")


def execute_clec_ops(ops: List[Dict[str, Any]], evidence: Dict[str, Any], verify: List[Dict[str, Any]] | None = None) -> Tuple[str, Dict[str, Any]]:
    if verify:
        _run_verify_checks(verify)

    out = dict(evidence or {})
    out.setdefault("logs", [])
    out.setdefault("hashes", {})
    out.setdefault("patches", [])
    out.setdefault("effects", [])

    side_effect_seen = False

    for idx, op in enumerate(ops):
        op_type = op.get("type")
        if op_type == "mkdir":
            target = _safe_join(str(op.get("target_path", "")))
            target.mkdir(parents=True, exist_ok=True)
            out["effects"].append(f"mkdir:{target}")
            side_effect_seen = True
        elif op_type == "copy":
            src = _safe_join(str(op.get("src_path", "")))
            dst = _safe_join(str(op.get("target_path", "")))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            out["effects"].append(f"copy:{src}->{dst}")
            side_effect_seen = True
        elif op_type == "write_text":
            target = _safe_join(str(op.get("target_path", "")))
            content = str(op.get("content", ""))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            out["hashes"][str(target.relative_to(ROOT))] = _sha256(target)
            out["effects"].append(f"write_text:{target}")
            side_effect_seen = True
        elif op_type == "patch_apply":
            target = _safe_join(str(op.get("target_path", "")))
            before = _sha256(target) if target.exists() and target.is_file() else ""
            patch_ref = str(op.get("patch_ref", "")).strip()
            if patch_ref:
                patch_path = _safe_join(patch_ref)
                if patch_path.exists() and patch_path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(patch_path.read_text(encoding="utf-8"), encoding="utf-8")
            after = _sha256(target) if target.exists() and target.is_file() else ""
            out["patches"].append(
                {
                    "op_index": idx,
                    "target": str(target.relative_to(ROOT)),
                    "before_sha256": before,
                    "after_sha256": after,
                }
            )
            out["effects"].append(f"patch_apply:{target}")
            side_effect_seen = True
        elif op_type == "run":
            command = str(op.get("command", "")).strip()
            if not _command_allowed(command):
                raise CLECExecutorError(f"command_not_allowed:index={idx}")
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                check=False,
            )
            out["logs"].append(
                {
                    "op_index": idx,
                    "command": command,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                }
            )
            out["effects"].append(f"run:{command}")
            side_effect_seen = True
        else:
            raise CLECExecutorError(f"unsupported_op_type:index={idx}")

    status = "ok"
    if side_effect_seen and not out.get("logs") and not out.get("hashes") and not out.get("patches"):
        status = "partial"
    return status, out

