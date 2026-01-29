#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOTFOUND = 4
EXIT_VALIDATE_FAIL = 8
EXIT_HEALTH_FAIL = 16
EXIT_STATUS_FAIL = 32


def _run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def _read_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema_version: {data.get('schema_version')}")
    
    # Support both array and dict formats for modules
    modules = data.get("modules")
    if isinstance(modules, list):
        # Convert array to dict keyed by label
        mods_dict = {}
        for m in modules:
            label = m.get("label", "")
            name = label.replace("com.0luka.", "").replace("-", "_").replace(".", "_")
            mods_dict[name] = {
                "launchd_label": label,
                "health_url": m.get("health_url"),
                "ports": [m["port"]] if m.get("port") else [],
                "notes": m.get("description", ""),
                "state": m.get("state", "deployed"),
            }
        data["modules"] = mods_dict
    elif not isinstance(modules, dict):
        raise ValueError("Invalid registry: modules must be dict or array")
    
    return data


def _uid() -> str:
    try:
        return str(os.getuid())
    except Exception:
        return "501"


def _launchctl_print(label: str) -> Tuple[bool, str]:
    # Prefer LaunchAgent domain (gui/<uid>), fallback to system domain
    uid = _uid()
    cp = _run(["launchctl", "print", f"gui/{uid}/{label}"])
    if cp.returncode == 0:
        return True, cp.stdout
    cp2 = _run(["launchctl", "print", f"system/{label}"])
    if cp2.returncode == 0:
        return True, cp2.stdout
    return False, (cp.stderr.strip() + ("\n" + cp2.stderr.strip() if cp2.stderr else "")).strip()


def _launchctl_bootstrap(label: str, plist_path: Optional[str]) -> Tuple[bool, str]:
    uid = _uid()
    if not plist_path:
        return False, "Missing plist_path for bootstrap"
    cp = _run(["launchctl", "bootstrap", f"gui/{uid}", plist_path])
    if cp.returncode == 0:
        return True, cp.stdout.strip()
    cp2 = _run(["launchctl", "bootstrap", "system", plist_path])
    if cp2.returncode == 0:
        return True, cp2.stdout.strip()
    return False, (cp.stderr.strip() + ("\n" + cp2.stderr.strip() if cp2.stderr else "")).strip()


def _launchctl_bootout(label: str, plist_path: Optional[str]) -> Tuple[bool, str]:
    uid = _uid()
    # bootout takes a domain + either label (preferred) or plist path
    # We try by label first in both domains; if that fails and plist_path exists, try plist.
    cp = _run(["launchctl", "bootout", f"gui/{uid}", f"gui/{uid}/{label}"])
    if cp.returncode == 0:
        return True, cp.stdout.strip()
    cp2 = _run(["launchctl", "bootout", "system", f"system/{label}"])
    if cp2.returncode == 0:
        return True, cp2.stdout.strip()
    if plist_path:
        cp3 = _run(["launchctl", "bootout", f"gui/{uid}", plist_path])
        if cp3.returncode == 0:
            return True, cp3.stdout.strip()
        cp4 = _run(["launchctl", "bootout", "system", plist_path])
        if cp4.returncode == 0:
            return True, cp4.stdout.strip()
        return False, (cp.stderr.strip() + ("\n" + cp2.stderr.strip() if cp2.stderr else "") + ("\n" + cp4.stderr.strip() if cp4.stderr else "")).strip()
    return False, (cp.stderr.strip() + ("\n" + cp2.stderr.strip() if cp2.stderr else "")).strip()


def _kickstart(label: str) -> Tuple[bool, str]:
    uid = _uid()
    cp = _run(["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"])
    if cp.returncode == 0:
        return True, cp.stdout.strip()
    cp2 = _run(["launchctl", "kickstart", "-k", f"system/{label}"])
    if cp2.returncode == 0:
        return True, cp2.stdout.strip()
    return False, (cp.stderr.strip() + ("\n" + cp2.stderr.strip() if cp2.stderr else "")).strip()


def _parse_pid(print_out: str) -> Optional[int]:
    # Works with launchctl print output format: "pid = 77777"
    m = re.search(r"\bpid\s*=\s*(\d+)\b", print_out)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _parse_state(print_out: str) -> Optional[str]:
    m = re.search(r"\bstate\s*=\s*([a-zA-Z0-9_\s]+)\b", print_out)
    return m.group(1).strip() if m else None


def _parse_exit_code(print_out: str) -> Optional[int]:
    m = re.search(r"\blast exit code\s*=\s*(\d+)", print_out)
    return int(m.group(1)) if m else None


def _port_listener_pid(port: int) -> Optional[int]:
    cp = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    if cp.returncode != 0 or not cp.stdout.strip():
        return None
    lines = [ln for ln in cp.stdout.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    # Header: COMMAND PID USER ...
    for ln in lines[1:]:
        cols = ln.split()
        if len(cols) >= 2 and cols[1].isdigit():
            return int(cols[1])
    return None


def _http_get(url: str, timeout: float = 3.0) -> Tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "0luka-modulectl/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (200 <= resp.status < 300), f"status={resp.status}"
    except Exception as e:
        return False, str(e)


def cmd_list(reg: Dict[str, Any]) -> int:
    mods = reg["modules"]
    names = sorted(mods.keys())
    for n in names:
        label = mods[n].get("launchd_label", "-")
        print(f"{n}\t{label}")
    return EXIT_OK


def cmd_status(reg: Dict[str, Any], name: str) -> int:
    mods = reg["modules"]
    # Handle 'all' - iterate through every module
    if name == "all":
        worst = EXIT_OK
        for mod_name in sorted(mods.keys()):
            print(f"--- {mod_name} ---")
            rc = cmd_status(reg, mod_name)
            worst = max(worst, rc)
        return worst
    if name not in mods:
        print(f"ERROR: module not found: {name}", file=sys.stderr)
        return EXIT_NOTFOUND
    m = mods[name]
    label = m.get("launchd_label")
    if not label:
        print("ERROR: missing launchd_label", file=sys.stderr)
        return EXIT_STATUS_FAIL

    ok, out = _launchctl_print(label)
    if not ok:
        print(f"Launchd: NOT LOADED ({label})")
        if out:
            print(out.strip())
    else:
        pid = _parse_pid(out)
        state = _parse_state(out) or "unknown"
        exit_code = _parse_exit_code(out)
        exit_str = f", last_exit={exit_code}" if exit_code is not None else ""
        print(f"Launchd: loaded, state={state}, PID={pid if pid else 'N/A'}{exit_str}")

    ports: List[int] = m.get("ports") or []
    if ports:
        for p in ports:
            lp = _port_listener_pid(int(p))
            if lp:
                print(f"Port {p}: in use (PID={lp})")
            else:
                print(f"Port {p}: not listening")
    else:
        print("Port: (none declared)")
    return EXIT_OK


def cmd_health(reg: Dict[str, Any], name: str) -> int:
    mods = reg["modules"]
    # Handle 'all' - iterate through modules with health_url
    if name == "all":
        worst = EXIT_OK
        for mod_name in sorted(mods.keys()):
            url = mods[mod_name].get("health_url")
            if url:
                print(f"--- {mod_name} ---")
                rc = cmd_health(reg, mod_name)
                worst = max(worst, rc)
            else:
                print(f"--- {mod_name} --- (no health_url, skipped)")
        return worst
    if name not in mods:
        print(f"ERROR: module not found: {name}", file=sys.stderr)
        return EXIT_NOTFOUND
    url = mods[name].get("health_url")
    if not url:
        print("SKIP: no health_url set for module")
        return EXIT_OK
    ok, msg = _http_get(url)
    if ok:
        print(f"OK: {msg}")
        return EXIT_OK
    print(f"FAIL: {msg}", file=sys.stderr)
    return EXIT_HEALTH_FAIL


def cmd_validate(reg: Dict[str, Any]) -> int:
    mods = reg["modules"]
    # collisions
    labels_seen: Dict[str, str] = {}
    ports_seen: Dict[int, str] = {}

    errors: List[str] = []

    root = reg.get("root")
    if not root or not Path(root).exists():
        errors.append(f"root missing or not exists: {root}")

    for name, m in mods.items():
        label = m.get("launchd_label")
        if not label:
            errors.append(f"{name}: missing launchd_label")
        else:
            if label in labels_seen:
                errors.append(f"launchd_label collision: {label} used by {labels_seen[label]} and {name}")
            labels_seen[label] = name

        ports = m.get("ports") or []
        for p in ports:
            try:
                pi = int(p)
            except Exception:
                errors.append(f"{name}: invalid port: {p}")
                continue
            if pi in ports_seen:
                errors.append(f"port collision: {pi} used by {ports_seen[pi]} and {name}")
            ports_seen[pi] = name

        # optional: health_url shape
        url = m.get("health_url")
        if url is not None and url != "" and not (isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))):
            errors.append(f"{name}: invalid health_url: {url}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_VALIDATE_FAIL

    print("✅ Registry valid")
    return EXIT_OK


def cmd_enable(reg: Dict[str, Any], name: str) -> int:
    mods = reg["modules"]
    if name not in mods:
        print(f"ERROR: module not found: {name}", file=sys.stderr)
        return EXIT_NOTFOUND
    m = mods[name]
    label = m.get("launchd_label")
    plist = m.get("plist_path")  # optional
    if plist:
        ok, msg = _launchctl_bootstrap(label, plist)
        if not ok:
            print(f"ERROR: bootstrap failed: {msg}", file=sys.stderr)
            return EXIT_STATUS_FAIL
    ok2, msg2 = _kickstart(label)
    if not ok2:
        print(f"ERROR: kickstart failed: {msg2}", file=sys.stderr)
        return EXIT_STATUS_FAIL
    print("OK: enabled")
    return EXIT_OK


def cmd_disable(reg: Dict[str, Any], name: str) -> int:
    mods = reg["modules"]
    if name not in mods:
        print(f"ERROR: module not found: {name}", file=sys.stderr)
        return EXIT_NOTFOUND
    m = mods[name]
    label = m.get("launchd_label")
    plist = m.get("plist_path")  # optional
    ok, msg = _launchctl_bootout(label, plist)
    if not ok:
        print(f"ERROR: bootout failed: {msg}", file=sys.stderr)
        return EXIT_STATUS_FAIL
    print("OK: disabled")
    return EXIT_OK


def usage() -> int:
    print(
        "Usage:\n"
        "  python3 core_brain/ops/modulectl.py list\n"
        "  python3 core_brain/ops/modulectl.py status <name|all>\n"
        "  python3 core_brain/ops/modulectl.py health <name|all>\n"
        "  python3 core_brain/ops/modulectl.py validate\n"
        "  python3 core_brain/ops/modulectl.py enable <name>\n"
        "  python3 core_brain/ops/modulectl.py disable <name>\n",
        file=sys.stderr,
    )
    return EXIT_USAGE


def main(argv: List[str]) -> int:
    ops_dir = Path(__file__).resolve().parent
    reg_path = ops_dir / "module_registry.json"
    try:
        reg = _read_registry(reg_path)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_VALIDATE_FAIL

    if len(argv) < 2:
        return usage()

    cmd = argv[1]
    if cmd == "list":
        return cmd_list(reg)
    if cmd == "validate":
        return cmd_validate(reg)
    if cmd in ("status", "health", "enable", "disable"):
        if len(argv) < 3:
            return usage()
        name = argv[2]
        if cmd == "status":
            return cmd_status(reg, name)
        if cmd == "health":
            return cmd_health(reg, name)
        if cmd == "enable":
            return cmd_enable(reg, name)
        if cmd == "disable":
            return cmd_disable(reg, name)
    return usage()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
