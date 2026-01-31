#!/usr/bin/env python3
# tools/librarian/utils.py
# Canonical helpers for Librarian automation (Approved v1 - R2 Compliant)

import hashlib
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Approved v1: PyYAML is a strict dependency (R2 Compliance)
try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    print("[FATAL] PyYAML is required but not installed. Install: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

def now_utc_iso() -> str:
    """Return current UTC timestamp as ISO8601. Example: 2026-01-30T19:45:00Z"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def file_checksum(path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def short_hash(s: str, length: int = 8) -> str:
    """Return short hash prefix for deterministic naming."""
    return s[:length] if len(s) >= length else s

def compute_move_id(src_path: Path, dst_path: Path, *, root: Path | None = None) -> str:
    """
    Meta-based deterministic move id (Approved v1 - A1 Compliance).
    No content hash (avoids reading files twice for ID only).
    """
    r = root.resolve() if root else None
    
    def _rel(p: Path) -> str:
        pr = p.resolve()
        if r:
            try:
                return str(pr.relative_to(r))
            except Exception:
                return str(p)
        return str(p)
    
    st = src_path.stat()
    size = st.st_size
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    
    try:
        inode = getattr(st, "st_ino", 0)
    except AttributeError:
        inode = 0
    
    dst_rel = _rel(dst_path) if dst_path else "none"
    src_rel = _rel(src_path)
    
    id_components = [
        f"src={short_hash(src_rel)}",
        f"dst={short_hash(dst_rel)}",
        f"sz={size}",
        f"mt={mtime_ns}",
        f"ino={inode}"
    ]
    
    payload = "|".join(id_components).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()

def write_yaml(path: Path, data: dict) -> None:
    """Write YAML deterministically (Approved v1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

def write_json(path: Path, data: dict) -> None:
    """Write JSON deterministically (Approved v1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def read_yaml(path: Path) -> dict:
    """Read YAML deterministically (Approved v1)."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
