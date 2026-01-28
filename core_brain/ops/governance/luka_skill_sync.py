#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _utc_ts() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _traceparent() -> str:
    # W3C traceparent: version(2)-traceid(32)-parentid(16)-flags(2)
    trace_id = os.urandom(16).hex()
    parent_id = os.urandom(8).hex()
    return f"00-{trace_id}-{parent_id}-01"


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_dir(root: Path) -> str:
    entries: List[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        name = p.name
        if name in {".DS_Store", ".gitignore"}:
            continue
        if "/.git/" in f"/{rel}":
            continue
        if "/__pycache__/" in f"/{rel}":
            continue
        entries.append(f"{rel}:{_hash_file(p)}")
    h = hashlib.sha256()
    h.update("\n".join(entries).encode("utf-8"))
    return h.hexdigest()


def _extract_metadata(skill_dir: Path) -> Dict[str, object]:
    candidates = [
        skill_dir / "SKILL.md",
        skill_dir / "skill.md",
        skill_dir / "README.md",
        skill_dir / "metadata.json",
    ]
    doc = next((p for p in candidates if p.exists()), None)
    if not doc:
        return {
            "desc": skill_dir.name.replace("-", " ").replace("_", " ").title(),
            "mandatory_read": False,
        }

    content = doc.read_text("utf-8", errors="ignore")
    lower_content = content.lower()
    mandatory = any(
        phrase in lower_content
        for phrase in (
            "mandatory",
            "critical",
            "read entire",
            "read-entire",
            "must read",
            "must-read",
        )
    )
    if doc.suffix == ".json":
        try:
            return {
                "desc": json.loads(content).get("description", "(no description in json)"),
                "mandatory_read": mandatory,
            }
        except Exception:
            return {"desc": "(broken json metadata)", "mandatory_read": mandatory}

    lines = content.splitlines()
    header_seen = False
    for raw in lines[:60]:
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(("description:", "role:", "purpose:", "**role:**", "**description:**")):
            return {
                "desc": line.split(":", 1)[1].strip().strip("*").strip()
                or "(no description)",
                "mandatory_read": mandatory,
            }
        if lower.startswith("#"):
            header_seen = True
            continue
        if header_seen and not line.startswith(("-", "*", "!", "[")):
            return {"desc": line, "mandatory_read": mandatory}

    return {"desc": "(no summary found)", "mandatory_read": mandatory}


def _skills(root: Path) -> List[Tuple[str, Path]]:
    out: List[Tuple[str, Path]] = []
    for p in sorted(root.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            out.append((p.name, p))
    return out


def _write_manifest(
    manifest: Path, linked_path: Path, library_path: Path, rows: List[Dict[str, str]]
) -> str:
    ts = _utc_ts()
    lines: List[str] = []
    lines.append("# 0luka Skill Manifest")
    lines.append(f"Generated: {ts}")
    lines.append(f"Base Path: `{library_path}`")
    lines.append(f"Linked Path: `{linked_path}`")
    lines.append("")
    lines.append("| Skill Name | Description | Mandatory Read | Integrity Hash (SHA256) |")
    lines.append("| :--- | :--- | :---: | :--- |")
    if rows:
        for r in rows:
            mandatory = "YES" if r["mandatory_read"] else "NO"
            lines.append(
                f"| `{r['name']}` | {r['desc']} | {mandatory} | `{r['hash']}` |"
            )
    else:
        lines.append("| (none) | (no skills found) | `-` |")
    lines.append("")
    lines.append("## Usage")
    lines.append("- Refer to each skill's SKILL.md for instructions.")
    lines.append("- If Mandatory Read is YES, ingest full skill docs before execution.")
    lines.append("- Keep skill folder names stable to preserve hashes.")
    content = "\n".join(lines) + "\n"

    tmp = manifest.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(manifest)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _append_beacon(beacon_path: Path, rec: Dict[str, object]) -> None:
    beacon_path.parent.mkdir(parents=True, exist_ok=True)
    with beacon_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate 0luka skill manifest")
    ap.add_argument("--root", default=os.environ.get("ROOT", str(Path.home() / "0luka")))
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    skills_link = root / "skills" / "shared"
    manifest = root / "skills" / "manifest.md"
    beacon = root / "observability/stl/ledger/global_beacon.jsonl"

    if not skills_link.exists():
        raise SystemExit(f"Skills link not found: {skills_link}")

    # resolve library path if possible
    try:
        library_path = skills_link.resolve()
    except Exception:
        library_path = skills_link

    rows: List[Dict[str, object]] = []
    for name, path in _skills(skills_link):
        meta = _extract_metadata(path)
        rows.append(
            {
                "name": name,
                "desc": str(meta.get("desc")),
                "mandatory_read": bool(meta.get("mandatory_read")),
                "hash": _hash_dir(path),
            }
        )

    manifest_hash = _write_manifest(manifest, skills_link, library_path, rows)
    ts = _utc_ts()
    rec = {
        "ts": ts,
        "event": "skills.manifest.updated",
        "ok": True,
        "skills_count": len(rows),
        "manifest_path": str(manifest),
        "manifest_hash": manifest_hash,
        "library_path": str(library_path),
        "linked_path": str(skills_link),
        "traceparent": _traceparent(),
    }
    _append_beacon(beacon, rec)
    print(f"OK: wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
