from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(data)
    os.replace(tmp, path)


def evidence_paths(repo_root: Path, task_id: str, day: str | None = None) -> Dict[str, Path]:
    d = day or utc_day()
    base_raw = repo_root / "observability" / "email_raw" / d
    base_run = repo_root / "observability" / "email_runs" / d / task_id
    return {
        "eml": base_raw / f"{task_id}.eml",
        "run_dir": base_run,
        "parsed": base_run / "parsed.yaml",
        "verdict": base_run / "verdict.json",
        "result": base_run / "result.json",
        "sha256": base_run / "sha256.txt",
    }


def write_raw_eml(paths: Dict[str, Path], eml_bytes: bytes) -> str:
    _atomic_write(paths["eml"], eml_bytes)
    digest = hashlib.sha256(eml_bytes).hexdigest()
    _atomic_write(paths["sha256"], (digest + "\n").encode("utf-8"))
    return digest


def write_parsed_yaml(paths: Dict[str, Path], yaml_text: str) -> None:
    _atomic_write(paths["parsed"], yaml_text.encode("utf-8"))


def write_json(paths: Dict[str, Path], key: str, payload: Dict[str, Any]) -> None:
    _atomic_write(paths[key], (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
