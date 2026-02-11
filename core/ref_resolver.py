from __future__ import annotations

import os
import platform
import re
import socket
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
DEFAULT_MAP_PATH = ROOT / "core/contracts/v1/ref_resolution.map.yaml"
_EXPR = re.compile(r"\$\{([^{}]+)\}")


def host_fingerprint() -> str:
    return f"{platform.system()}-{platform.machine()}-{socket.gethostname()}"


def _expand_expr(text: str) -> str:
    value = text
    for _ in range(12):
        match = _EXPR.search(value)
        if not match:
            break
        token = match.group(1)
        if ":-" in token:
            var, fallback = token.split(":-", 1)
            repl = os.environ.get(var, "") or fallback
        else:
            repl = os.environ.get(token, "")
        value = value[: match.start()] + repl + value[match.end() :]
    return os.path.expandvars(value)


def load_ref_map(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("missing dependency: pyyaml (pip install pyyaml)")
    if not path.exists():
        raise FileNotFoundError(f"map_not_found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("invalid_ref_map")
    return data


def _select_host(cfg: Dict[str, Any], fp: str) -> Dict[str, Any]:
    hosts = cfg.get("hosts") or {}
    for name, spec in hosts.items():
        if name == "default" or not isinstance(spec, dict):
            continue
        expected = spec.get("fingerprint_contains") or []
        if all(str(bit) in fp for bit in expected):
            return spec
    default = hosts.get("default")
    if not isinstance(default, dict):
        raise ValueError("host_default_missing")
    return default


def resolve_ref(ref: str, *, map_path: Optional[str] = None) -> Dict[str, Any]:
    if not ref.startswith("ref://"):
        raise ValueError("invalid_ref_scheme")
    if any(part == ".." for part in ref.split("/")):
        raise ValueError("invalid_ref_traversal")

    source_path = Path(map_path).expanduser() if map_path else DEFAULT_MAP_PATH
    cfg = load_ref_map(source_path)
    refs = cfg.get("refs") or {}
    if ref not in refs:
        raise KeyError(f"unknown_ref: {ref}")

    fp = host_fingerprint()
    host_cfg = _select_host(cfg, fp)
    root_raw = str(host_cfg.get("root", "")).strip()
    root_text = _expand_expr(root_raw)
    if not root_text:
        raise ValueError("root_unresolved")
    root = Path(root_text).expanduser().resolve(strict=False)

    mapped = str(refs[ref]).replace("${root}", str(root))
    path_text = _expand_expr(mapped)
    target = Path(path_text).expanduser().resolve(strict=False)
    if target != root and root not in target.parents:
        raise ValueError("ref_outside_root")

    return {
        "ref": ref,
        "kind": "path",
        "uri": target.as_uri(),
        "trust": True,
        "source": "ref://contracts/v1/ref_resolution.map.yaml",
    }


def resolve_path(ref: str, *, map_path: Optional[str] = None) -> Path:
    resolved = resolve_ref(ref, map_path=map_path)
    uri = str(resolved.get("uri", ""))
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"unsupported_uri_scheme:{parsed.scheme}")
    return Path(unquote(parsed.path))
