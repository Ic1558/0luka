#!/usr/bin/env python3
"""
TK Evidence Pack Builder (v1)
Creates a copy-only, deterministic, audit-ready evidence pack for incidents.

Usage:
    python3 system/tools/tk/tk_evidence_pack.py \
      --root ~/0luka \
      --kind module_not_running \
      --module com.0luka.session_recorder \
      --rc 64
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd: list) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output or ""
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, str(e)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_if_exists(root: Path, rel: str, dest_dir: Path, missing: list) -> str | None:
    src = root / rel
    if src.exists():
        dest = dest_dir / Path(rel).name
        dest.write_bytes(src.read_bytes())
        return dest.name
    missing.append(rel)
    return None


def _tail_file(path: Path, lines: int = 50) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return "\n".join(content.splitlines()[-lines:])
    except Exception:
        return ""


def main() -> int:
    args = sys.argv[1:]

    def get(flag: str, default: str | None = None) -> str | None:
        if flag in args:
            i = args.index(flag)
            return args[i + 1] if i + 1 < len(args) else default
        return default

    root = Path(os.path.expanduser(get("--root", "") or "")).resolve()
    kind = get("--kind", "unknown") or "unknown"
    module = get("--module")
    rc = get("--rc")
    incident_id = get("--incident-id")
    extra_json = get("--extra")

    if not root or not (root / "observability").exists():
        print("ERROR: --root must point to 0luka repo root (contains observability/)")
        return 2

    ts = _utc_ts()
    if not incident_id:
        incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    out_dir = root / "observability" / "artifacts" / "incidents" / incident_id
    out_dir.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    artifacts: dict[str, str | None] = {}

    # 1) launchd status snapshot
    if module:
        rc1, txt = _run(["launchctl", "print", f"gui/{os.getuid()}/{module}"])
        _write_text(out_dir / "launchd_status.txt", txt)
        artifacts["launchd_status"] = "launchd_status.txt"
    else:
        rc1, txt = _run(["launchctl", "list"])
        _write_text(out_dir / "launchctl_list.txt", txt)
        artifacts["launchctl_list"] = "launchctl_list.txt"

    # 2) ports listening (best-effort)
    rc2, txt2 = _run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
    _write_text(out_dir / "ports_listen.txt", txt2)
    artifacts["ports_listen"] = "ports_listen.txt"

    # 3) modulectl status all (best-effort)
    modulectl_path = root / "core_brain" / "ops" / "modulectl.py"
    if modulectl_path.exists():
        rc3, txt3 = _run(["python3", str(modulectl_path), "status", "all"])
        _write_text(out_dir / "modulectl_status_all.txt", txt3)
        artifacts["modulectl_status_all"] = "modulectl_status_all.txt"

    # 4) telemetry copies (best-effort)
    artifacts["tk_health"] = _copy_if_exists(
        root, "observability/telemetry/tk_health.latest.json", out_dir, missing
    )
    artifacts["ram_monitor"] = _copy_if_exists(
        root, "observability/telemetry/ram_monitor.latest.json", out_dir, missing
    )

    # 5) log tails (best-effort, if module is known)
    if module:
        label_clean = module.replace("com.0luka.", "").replace("_", "-")
        stdout_path = root / "observability" / "logs" / f"{label_clean}.stdout.log"
        stderr_path = root / "observability" / "logs" / f"{label_clean}.stderr.log"
        
        stdout_tail = _tail_file(stdout_path)
        stderr_tail = _tail_file(stderr_path)
        
        if stdout_tail:
            _write_text(out_dir / "stdout_tail.log", stdout_tail)
            artifacts["stdout_tail"] = "stdout_tail.log"
        if stderr_tail:
            _write_text(out_dir / "stderr_tail.log", stderr_tail)
            artifacts["stderr_tail"] = "stderr_tail.log"

    # 6) incident.json (manifest)
    extra = None
    if extra_json:
        try:
            extra = json.loads(extra_json)
        except Exception:
            extra = {"raw": extra_json}

    manifest = {
        "schema_version": "tk_evidence_pack.v1",
        "incident_id": incident_id,
        "generated_at": ts,
        "root": str(root),
        "kind": kind,
        "module": module,
        "rc": int(rc) if rc and rc.isdigit() else rc,
        "artifacts": {k: v for k, v in artifacts.items() if v},
        "missing": missing,
        "extra": extra,
    }
    (out_dir / "incident.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
