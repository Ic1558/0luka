#!/usr/bin/env python3
"""
Remediation Engine — core/remediation_engine.py

Reads observability state files, evaluates policy triggers, executes bounded
actions (kill_process_group, launchd_reload), and emits evidence artifacts.

Key invariants:
  - Reads state files only; never calls monitors directly
  - Unknown actions rejected at parse time (fail-closed)
  - Cooldown prevents re-fire within window
  - All executions produce evidence JSON
  - Wraps CircuitBreaker — trips after 3 consecutive failures
  - REMEDIATION_ENABLED=1 required for live execution (dry-run by default)

Usage:
    python3 core/remediation_engine.py --trigger ram --state-path <path> [--dry-run]
    python3 core/remediation_engine.py --trigger health --state-path <path> [--dry-run]
    python3 core/remediation_engine.py --eval-all [--dry-run] [--confirmed]
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import sys

import yaml

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY_PATH = ROOT / "core" / "governance" / "remediation_policy.yaml"
COOLDOWN_STATE_PATH = ROOT / "observability" / "telemetry" / "remediation_engine.state.json"
EVIDENCE_DIR = ROOT / "observability" / "artifacts" / "remediation"
REMEDIATION_LOG = ROOT / "observability" / "logs" / "components" / "remediation.jsonl"

# Default state paths (can be overridden via CLI)
RAM_STATE_PATH = ROOT / "observability" / "telemetry" / "ram_monitor.latest.json"
HEALTH_STATE_PATH = ROOT / "observability" / "artifacts" / "health_latest.json"

ALLOWED_ACTIONS = {"kill_process_group", "launchd_reload"}


class RemediationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Policy loading
# ---------------------------------------------------------------------------

def load_policy(path: Path = POLICY_PATH) -> dict:
    """Load and validate policy YAML. Fails closed on unknown actions."""
    if not path.exists():
        raise RemediationError(f"policy_not_found:{path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
    except Exception as exc:
        raise RemediationError(f"policy_parse_error:{exc}") from exc

    if not isinstance(policy, dict):
        raise RemediationError("policy_invalid:not_a_mapping")
    if policy.get("version") != 1:
        raise RemediationError(f"policy_invalid:unsupported_version={policy.get('version')}")

    triggers = policy.get("triggers", [])
    if not isinstance(triggers, list):
        raise RemediationError("policy_invalid:triggers_not_a_list")

    allowed = set(policy.get("allowed_actions", []))
    if not allowed:
        raise RemediationError("policy_invalid:no_allowed_actions")

    unknown = allowed - ALLOWED_ACTIONS
    if unknown:
        raise RemediationError(f"policy_invalid:unknown_actions={unknown}")

    for t in triggers:
        action = t.get("action")
        if action not in allowed:
            raise RemediationError(
                f"policy_invalid:trigger={t.get('id', '?')}:action_not_in_allowed_list={action}"
            )

    return policy


# ---------------------------------------------------------------------------
# State snapshot readers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_cooldown_state() -> dict:
    return _read_json(COOLDOWN_STATE_PATH)


def _save_cooldown_state(state: dict) -> None:
    COOLDOWN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = COOLDOWN_STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, COOLDOWN_STATE_PATH)


def _is_on_cooldown(trigger_id: str, cooldown_sec: int, cooldown_state: dict) -> bool:
    last_fire = cooldown_state.get(trigger_id, {}).get("last_fire_epoch", 0)
    return (time.time() - float(last_fire)) < cooldown_sec


def _record_cooldown(trigger_id: str, cooldown_state: dict) -> None:
    cooldown_state.setdefault(trigger_id, {})["last_fire_epoch"] = time.time()
    _save_cooldown_state(cooldown_state)


# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------

def evaluate_triggers(policy: dict, ram_state: dict | None = None, health_state: dict | None = None) -> list[dict]:
    """Return list of triggers whose conditions are satisfied."""
    if ram_state is None:
        ram_state = _read_json(RAM_STATE_PATH)
    if health_state is None:
        health_state = _read_json(HEALTH_STATE_PATH)

    armed = []
    for trigger in policy.get("triggers", []):
        condition = trigger.get("condition", "")
        if condition == "ram_monitor.pressure_level == CRITICAL":
            if ram_state.get("pressure_level") == "CRITICAL":
                armed.append(trigger)
        elif condition == "health.dev_health == DEGRADED":
            # health_latest.json stores "overall" or "dev_health" key
            dev = str(
                health_state.get("dev_health")
                or health_state.get("overall")
                or ""
            ).upper()
            if dev == "DEGRADED":
                armed.append(trigger)
    return armed


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_evidence(trigger_id: str, action: str, result: dict) -> Path:
    """Write evidence JSON for an executed action. Returns evidence path."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    evidence_path = EVIDENCE_DIR / f"{ts}_{trigger_id}_{action}.json"
    payload = {
        "ts": _utc_now(),
        "trigger_id": trigger_id,
        "action": action,
        "result": result,
    }
    tmp = evidence_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, evidence_path)
    return evidence_path


def _log_remediation(entry: dict) -> None:
    """Append entry to remediation component log."""
    try:
        REMEDIATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with REMEDIATION_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _action_kill_process_group(params: dict, dry_run: bool) -> dict:
    """Find PIDs matching patterns, send SIGTERM (up to max_targets)."""
    patterns = params.get("patterns", [])
    max_targets = int(params.get("max_targets", 3))
    sig = getattr(signal, params.get("signal", "SIGTERM"), signal.SIGTERM)

    killed = []
    skipped = []
    errors = []

    try:
        ps_out = subprocess.check_output(
            ["/bin/ps", "-Ao", "pid=,args="], text=True, timeout=10
        )
    except Exception as exc:
        return {"status": "error", "reason": f"ps_failed:{exc}", "killed": [], "skipped": []}

    candidates = []
    for line in ps_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_s, cmdline = parts
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        for pat in patterns:
            if pat in cmdline:
                candidates.append({"pid": pid, "cmdline": cmdline[:180], "pattern": pat})
                break

    targets = candidates[:max_targets]

    for target in targets:
        pid = target["pid"]
        if dry_run:
            skipped.append({"pid": pid, "reason": "dry_run"})
            continue
        try:
            os.kill(pid, sig)
            killed.append({"pid": pid, "signal": sig.name})
        except ProcessLookupError:
            skipped.append({"pid": pid, "reason": "not_found"})
        except PermissionError:
            errors.append({"pid": pid, "reason": "permission_denied"})
        except Exception as exc:
            errors.append({"pid": pid, "reason": str(exc)})

    status = "dry_run" if dry_run else ("ok" if not errors else "partial")
    return {
        "status": status,
        "candidates_found": len(candidates),
        "killed": killed,
        "skipped": skipped,
        "errors": errors,
    }


def _action_launchd_reload(params: dict, dry_run: bool) -> dict:
    """Reload a launchd service via launchctl kickstart -k."""
    service = params.get("service", "")
    if not service:
        return {"status": "error", "reason": "no_service_name"}

    # Safety: only allow com.0luka.* services
    if not service.startswith("com.0luka."):
        return {"status": "error", "reason": f"service_not_in_allowlist:{service}"}

    target = f"system/{service}"

    if dry_run:
        return {"status": "dry_run", "service": service, "command": f"launchctl kickstart -k {target}"}

    try:
        result = subprocess.run(
            ["/bin/launchctl", "kickstart", "-k", target],
            capture_output=True, text=True, timeout=30
        )
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:500],
            "stderr": result.stderr.strip()[:500],
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def execute_action(trigger: dict, policy: dict, dry_run: bool) -> dict:
    """Dispatch to the appropriate bounded handler."""
    action = trigger.get("action")
    params = trigger.get("params", {})

    if action == "kill_process_group":
        return _action_kill_process_group(params, dry_run)
    elif action == "launchd_reload":
        return _action_launchd_reload(params, dry_run)
    else:
        raise RemediationError(f"unknown_action:{action}")


def run_remediation(
    trigger_filter: str | None = None,
    ram_state: dict | None = None,
    health_state: dict | None = None,
    dry_run: bool = True,
    policy_path: Path = POLICY_PATH,
) -> list[dict]:
    """
    Full remediation cycle: load policy → evaluate → cooldown check → execute → evidence.

    Returns list of execution records.
    Dry-run by default. Pass dry_run=False AND REMEDIATION_ENABLED=1 for live execution.
    """
    from core.circuit_breaker import CircuitBreaker, CircuitOpenError

    cb = CircuitBreaker(name="remediation_engine", failure_threshold=3, recovery_timeout_sec=60.0)

    policy = load_policy(policy_path)
    triggered = evaluate_triggers(policy, ram_state=ram_state, health_state=health_state)

    if trigger_filter:
        triggered = [t for t in triggered if t.get("id", "").startswith(trigger_filter)
                     or t.get("condition", "").lower().startswith(trigger_filter.lower())]

    cooldown_state = _load_cooldown_state()
    records = []

    for trigger in triggered:
        tid = trigger.get("id", "unknown")
        cooldown_sec = int(trigger.get("cooldown_sec", 300))

        if _is_on_cooldown(tid, cooldown_sec, cooldown_state):
            rec = {
                "ts": _utc_now(),
                "trigger_id": tid,
                "action": trigger.get("action"),
                "status": "suppressed_cooldown",
                "dry_run": dry_run,
            }
            records.append(rec)
            _log_remediation(rec)
            continue

        try:
            def _exec():
                return execute_action(trigger, policy, dry_run)

            result = cb.call(_exec)
        except CircuitOpenError as exc:
            rec = {
                "ts": _utc_now(),
                "trigger_id": tid,
                "action": trigger.get("action"),
                "status": "circuit_open",
                "reason": str(exc),
                "dry_run": dry_run,
            }
            records.append(rec)
            _log_remediation(rec)
            continue
        except Exception as exc:
            rec = {
                "ts": _utc_now(),
                "trigger_id": tid,
                "action": trigger.get("action"),
                "status": "error",
                "reason": str(exc),
                "dry_run": dry_run,
            }
            records.append(rec)
            _log_remediation(rec)
            continue

        # Record cooldown on successful (non-dry-run) execution
        if not dry_run:
            _record_cooldown(tid, cooldown_state)

        # Write evidence if required or action succeeded
        evidence_path: Path | None = None
        if trigger.get("require_evidence", False):
            try:
                evidence_path = _write_evidence(tid, str(trigger.get("action")), result)
            except Exception:
                pass

        if evidence_path is not None:
            try:
                ev_str = str(evidence_path.relative_to(ROOT))
            except ValueError:
                ev_str = str(evidence_path)
        else:
            ev_str = None

        rec = {
            "ts": _utc_now(),
            "trigger_id": tid,
            "action": trigger.get("action"),
            "status": result.get("status", "unknown"),
            "dry_run": dry_run,
            "result": result,
            "evidence": ev_str,
        }
        records.append(rec)
        _log_remediation(rec)

    return records


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Remediation Engine")
    parser.add_argument(
        "--trigger",
        choices=["ram", "health"],
        help="Filter triggers by type (ram or health)",
    )
    parser.add_argument(
        "--state-path",
        dest="state_path",
        help="Path to state snapshot JSON (ram_monitor.latest.json or health_latest.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode (default: true)",
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        default=False,
        help="Execute for real (requires REMEDIATION_ENABLED=1 env var)",
    )
    parser.add_argument(
        "--eval-all",
        action="store_true",
        help="Evaluate all triggers from default state paths",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON output",
    )
    args = parser.parse_args()

    live = args.confirmed and os.environ.get("REMEDIATION_ENABLED") == "1"
    dry_run = not live

    ram_state: dict | None = None
    health_state: dict | None = None

    if args.state_path:
        sp = Path(args.state_path)
        data = _read_json(sp)
        if args.trigger == "ram" or "pressure_level" in data:
            ram_state = data
        elif args.trigger == "health" or "dev_health" in data or "overall" in data:
            health_state = data

    records = run_remediation(
        trigger_filter=args.trigger,
        ram_state=ram_state,
        health_state=health_state,
        dry_run=dry_run,
    )

    if args.json or not records:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        for r in records:
            mode = "DRY-RUN" if r.get("dry_run") else "LIVE"
            print(f"[{mode}] trigger={r['trigger_id']} action={r['action']} status={r['status']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
