import json, os, re, subprocess, time
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).resolve()
MODULECTL = ROOT / "core_brain" / "ops" / "modulectl.py"

IDLE_ALLOWLIST = set(os.environ.get("TK_IDLE_ALLOWLIST", "").split(",")) if os.environ.get("TK_IDLE_ALLOWLIST") else set()

TELE = ROOT / "observability" / "telemetry" / "tk_health.latest.json"
INC = ROOT / "observability" / "incidents" / "tk_incidents.jsonl"

def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout

def parse_status_block(text: str) -> dict:
    # Expected lines (from your output):
    # Launchd: loaded, state=running, PID=1163
    # Port 7001: in use (PID=78667)  OR  Port: (none declared)
    out = {"loaded": None, "state": None, "pid": None, "port": None, "port_pid": None, "last_exit": None}
    m = re.search(r"Launchd:\s+loaded,\s+state=([^,]+),\s+PID=([^,\n]+)", text)
    if m:
        out["loaded"] = True
        out["state"] = m.group(1).strip().lower()
        pid = m.group(2).strip()
        out["pid"] = None if pid in ("N/A", "-", "") else pid
    
    em = re.search(r"last_exit=(\d+)", text)
    if em:
        out["last_exit"] = int(em.group(1))

    pm = re.search(r"Port\s+([0-9]+):\s+in use\s+\(PID=([0-9]+)\)", text)
    if pm:
        out["port"] = int(pm.group(1))
        out["port_pid"] = int(pm.group(2))
    return out

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def main() -> int:
    if not MODULECTL.exists():
        print(f"ERROR: modulectl not found: {MODULECTL}")
        return 64

    rc, mods_txt = run(["python3", str(MODULECTL), "list"])
    if rc != 0:
        print(mods_txt)
        return 64

    # list output is: name<TAB>label - extract name only
    mods = [m.split("\t")[0].strip() for m in mods_txt.splitlines() if m.strip()]
    results = []
    incidents = []
    ts = now_utc_iso()

    # status per module
    for m in mods:
        rc, st = run(["python3", str(MODULECTL), "status", m])
        status = parse_status_block(st)
        status["name"] = m
        status["raw"] = st.strip()
        results.append(status)

        state = (status.get("state") or "").lower()
        # Periodic Success: loaded but not running + last_exit=0
        is_periodic_ok = (state == "not running" and status.get("last_exit") == 0)
        is_running = (state == "running")
        
        if state == "idle":
            if m not in IDLE_ALLOWLIST:
                incidents.append({
                    "ts": ts,
                    "kind": "module_idle_not_allowlisted",
                    "module": m,
                    "state": status.get("state"),
                    "pid": status.get("pid"),
                })
        elif not is_running and not is_periodic_ok:
            if m not in IDLE_ALLOWLIST:
                incidents.append({
                    "ts": ts,
                    "kind": "module_not_running",
                    "module": m,
                    "state": status.get("state"),
                    "pid": status.get("pid"),
                    "last_exit": status.get("last_exit"),
                })

        # port ownership sanity (only if declared)
        if status.get("port") is not None and status.get("port_pid") is not None:
            # If module has PID and port PID doesn't match => incident
            if status.get("pid") not in (None, "N/A") and str(status["port_pid"]) != str(status["pid"]):
                incidents.append({
                    "ts": ts,
                    "kind": "port_owner_mismatch",
                    "module": m,
                    "port": status["port"],
                    "expected_pid": status.get("pid"),
                    "actual_pid": status["port_pid"],
                })

    # health all (best-effort; enforce only if module defines health_url internally)
    # We treat nonzero exit as incident for the module(s) mentioned in output.
    rc, health_out = run(["python3", str(MODULECTL), "health", "all"])
    health_fail = (rc != 0)
    if health_fail:
        # try to extract module names from output lines like: "--- opal_api ---" or "opal_api"
        for line in health_out.splitlines():
            line = line.strip()
            if not line:
                continue
            # crude: mark generic incident; modulectl already prints which failed
        incidents.append({
            "ts": ts,
            "kind": "health_check_failed",
            "detail": health_out.strip()[:2000]
        })

    payload = {
        "ts": ts,
        "root": str(ROOT),
        "idle_allowlist": sorted([x for x in IDLE_ALLOWLIST if x]),
        "modules_total": len(mods),
        "modules": results,
        "health_all_rc": rc,
        "health_all_ok": (rc == 0),
    }
    TELE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if incidents:
        INC.parent.mkdir(parents=True, exist_ok=True)
        with INC.open("a", encoding="utf-8") as f:
            for ev in incidents:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # Exit codes:
    # 0 = all ok
    # 2 = only allowlisted idle (no incident)
    # 64 = incident
    if incidents:
        print("INCIDENT: ", len(incidents))
        return 64

    # detect degraded-only (allowlisted idle exists)
    degraded = any(((r.get("state") or "").lower() != "running") and (r["name"] in IDLE_ALLOWLIST) for r in results)
    if degraded:
        print("DEGRADED (allowlisted idle): ok")
        return 2

    print("OK: all required modules running + health ok")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
