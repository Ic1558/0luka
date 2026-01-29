import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).resolve()
MODULECTL = ROOT / "core_brain" / "ops" / "modulectl.py"
PLAYBOOK = ROOT / "system" / "tools" / "tk" / "incident_playbook.json"
EVIDENCE_PACK = ROOT / "system" / "tools" / "tk" / "tk_evidence_pack.py"

IDLE_ALLOWLIST = set(os.environ.get("TK_IDLE_ALLOWLIST", "").split(",")) if os.environ.get("TK_IDLE_ALLOWLIST") else set()

TELE = ROOT / "observability" / "telemetry" / "tk_health.latest.json"
INC = ROOT / "observability" / "incidents" / "tk_incidents.jsonl"
STATE_PATH = ROOT / "observability" / "telemetry" / "tk_guard.state.json"
DEBOUNCE_SEC = int(os.environ.get("TK_DEBOUNCE_SEC", "180"))


def load_debounce_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_incident": {}}


def save_debounce_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def should_debounce(state: dict, key: str, now_ts: str, cooldown_sec: int = 180) -> bool:
    """Return True if we should skip this incident due to recent occurrence."""
    last = state.get("last_incident", {}).get(key)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(now_ts.replace("Z", "+00:00"))
        return (now_dt - last_dt).total_seconds() < cooldown_sec
    except Exception:
        return False


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, str(e)


def parse_status_block(text: str) -> dict:
    out = {"loaded": None, "state": None, "pid": None, "port": None, "port_pid": None, "last_exit": None}
    m = re.search(r"Launchd:\s+loaded,\s+state=([^,]+),\s+PID=([^,\n]+)", text)
    if m:
        out["loaded"] = True
        out["state"] = m.group(1).strip().lower()
        pid = m.group(2).strip()
        if pid in ("N/A", "-", ""):
            out["pid"] = None
        elif pid.isdigit():
            out["pid"] = int(pid)
        else:
            out["pid"] = None

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


def resolve_launchd_label(module_name: str) -> str:
    """Convert short module name to full launchd label."""
    # Load registry to find actual label
    registry_path = ROOT / "core_brain" / "ops" / "module_registry.json"
    if registry_path.exists():
        try:
            reg = json.loads(registry_path.read_text(encoding="utf-8"))
            for mod in reg.get("modules", []):
                if mod.get("name") == module_name:
                    return mod.get("label", f"com.0luka.{module_name}")
        except Exception:
            pass
    # Fallback: derive label from name
    return f"com.0luka.{module_name}"


def load_playbook() -> dict | None:
    if not PLAYBOOK.exists():
        return None
    try:
        return json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    except Exception:
        return None


def match_rule(playbook: dict, incident: dict) -> dict | None:
    """Find first matching rule for incident."""
    rules = playbook.get("rules", [])
    kind = incident.get("kind", "")
    module = incident.get("module", "")

    for rule in rules:
        when = rule.get("when", {})
        if when.get("kind") != kind:
            continue
        module_regex = when.get("module_regex", ".*")
        if module and not re.match(module_regex, module):
            continue
        return rule
    return None


def is_module_allowed(playbook: dict, module: str) -> bool:
    """Check if module is in allow_actions_for_modules."""
    allowed = playbook.get("allow_actions_for_modules", [])
    return module in allowed


def create_evidence_pack(incident: dict) -> str | None:
    """Call evidence pack builder and return output dir."""
    if not EVIDENCE_PACK.exists():
        return None
    cmd = [
        "python3", str(EVIDENCE_PACK),
        "--root", str(ROOT),
        "--kind", incident.get("kind", "unknown"),
    ]
    if incident.get("module"):
        cmd.extend(["--module", incident["module"]])
    if incident.get("rc"):
        cmd.extend(["--rc", str(incident["rc"])])
    cmd.extend(["--extra", json.dumps(incident)])

    rc, out = run(cmd)
    if rc == 0 and out.strip():
        return out.strip()
    return None


def execute_action(playbook: dict, rule: dict, incident: dict) -> dict:
    """Execute the action from the matched rule."""
    action = rule.get("action", {})
    action_type = action.get("type", "no_op")

    result = {
        "type": action_type,
        "executed": False,
        "rc": None,
        "output": None,
    }

    if action_type == "no_op":
        result["reason"] = action.get("reason", "No action defined")
        return result

    module = incident.get("module")
    if not module:
        result["reason"] = "No module in incident"
        return result

    if not is_module_allowed(playbook, module):
        result["reason"] = f"Module {module} not in allow_actions_for_modules"
        return result

    if action_type == "launchd_kickstart":
        args = action.get("args", [])
        uid = os.getuid()
        launchd_label = resolve_launchd_label(module)

        # Try multiple domains: gui → user → system
        targets = [
            f"gui/{uid}/{launchd_label}",
            f"user/{uid}/{launchd_label}",
            f"system/{launchd_label}",
        ]

        last_rc, last_out, last_cmd = None, "", ""
        for target in targets:
            cmd = ["launchctl", "kickstart"] + args + [target]
            rc, out = run(cmd)
            last_rc, last_out, last_cmd = rc, out, " ".join(cmd)
            if rc == 0:
                result["executed"] = True
                result["rc"] = rc
                result["output"] = out.strip()[:500]
                result["cmd"] = last_cmd
                result["launchd_label"] = launchd_label
                result["target"] = target
                return result

        # all failed - return last attempt
        result["executed"] = True
        result["rc"] = last_rc
        result["output"] = (last_out or "").strip()[:500]
        result["cmd"] = last_cmd
        result["launchd_label"] = launchd_label
        result["target"] = targets[-1]
        return result


    elif action_type == "modulectl_enable":
        cmd = ["python3", str(MODULECTL), "enable", module]
        rc, out = run(cmd)
        result["executed"] = True
        result["rc"] = rc
        result["output"] = out.strip()[:500]
        result["cmd"] = " ".join(cmd)

    return result


def main() -> int:
    if not MODULECTL.exists():
        print(f"ERROR: modulectl not found: {MODULECTL}")
        return 64

    rc, mods_txt = run(["python3", str(MODULECTL), "list"])
    if rc != 0:
        print(mods_txt)
        return 64

    mods = [m.split("\t")[0].strip() for m in mods_txt.splitlines() if m.strip()]
    results = []
    incidents = []
    ts = now_utc_iso()
    debounce_state = load_debounce_state()

    # status per module
    for m in mods:
        rc, st = run(["python3", str(MODULECTL), "status", m])
        status = parse_status_block(st)
        status["name"] = m
        status["raw"] = st.strip()
        results.append(status)

        state = (status.get("state") or "").lower()
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
                # Debounce during spawn/transient states
                debounce_key = f"{m}|module_not_running"
                is_spawn = "spawn" in state
                if is_spawn and should_debounce(debounce_state, debounce_key, ts, DEBOUNCE_SEC):
                    pass  # Skip - recently logged, module is recovering
                else:
                    incidents.append({
                        "ts": ts,
                        "kind": "module_not_running",
                        "module": m,
                        "state": status.get("state"),
                        "pid": status.get("pid"),
                        "last_exit": status.get("last_exit"),
                    })
                    debounce_state.setdefault("last_incident", {})[debounce_key] = ts

        # port ownership sanity
        if status.get("port") is not None and status.get("port_pid") is not None:
            if status.get("pid") is not None and status["port_pid"] != status.get("pid"):
                incidents.append({
                    "ts": ts,
                    "kind": "port_owner_mismatch",
                    "module": m,
                    "port": status["port"],
                    "expected_pid": status.get("pid"),
                    "actual_pid": status["port_pid"],
                })

    # health all
    rc, health_out = run(["python3", str(MODULECTL), "health", "all"])
    health_fail = (rc != 0)
    if health_fail:
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

    # Process incidents through playbook
    playbook = load_playbook()
    processed_incidents = []

    for inc in incidents:
        inc_record = inc.copy()

        # Create evidence pack
        evidence_dir = create_evidence_pack(inc)
        if evidence_dir:
            inc_record["evidence_dir"] = evidence_dir

        # Match and execute playbook rule
        if playbook:
            rule = match_rule(playbook, inc)
            if rule:
                action_result = execute_action(playbook, rule, inc)
                inc_record["playbook_rule"] = rule.get("when", {})
                inc_record["playbook_action"] = action_result

        processed_incidents.append(inc_record)

    # Write processed incidents to log
    if processed_incidents:
        INC.parent.mkdir(parents=True, exist_ok=True)
        with INC.open("a", encoding="utf-8") as f:
            for ev in processed_incidents:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # Save debounce state
    save_debounce_state(debounce_state)

    # Exit codes: 0=ok, 2=degraded, 64=incident
    if incidents:
        print(f"INCIDENT: {len(incidents)}")
        return 64

    degraded = any(((r.get("state") or "").lower() != "running") and (r["name"] in IDLE_ALLOWLIST) for r in results)
    if degraded:
        print("DEGRADED (allowlisted idle): ok")
        return 2

    print("OK: all required modules running + health ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
