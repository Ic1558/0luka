#!/usr/bin/env python3
import json, sys, time, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.home() / "0luka"
SESSION_JSON = ROOT / "g/session/session_state.latest.json"
SESSION_MD   = ROOT / "g/session/SESSION_STATE.md"
OUT_DIR     = ROOT / "interface/plans"
TELEMETRY_PATH = ROOT / "observability/telemetry/liam_planner.latest.json"

def warn(msg):
    print(f"[LIAM][WARN] {msg}", file=sys.stderr)

def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

# --- Preflight (Warn-only) ---
precheck_errors = []
precheck_degraded = False
state = {}
ttl_sec = int(os.environ.get("SESSION_STATE_TTL_SEC", "120"))

if not SESSION_JSON.exists():
    warn("SESSION_STATE missing; continuing in degraded mode")
    precheck_errors.append("SESSION_STATE missing")
    precheck_degraded = True
else:
    try:
        state = json.loads(SESSION_JSON.read_text())
    except Exception as e:
        warn(f"SESSION_STATE invalid JSON: {e}; continuing in degraded mode")
        precheck_errors.append("SESSION_STATE invalid JSON")
        precheck_degraded = True

ts = state.get("ts_utc")
if not ts:
    warn("SESSION_STATE invalid (no ts_utc); continuing in degraded mode")
    precheck_errors.append("SESSION_STATE missing ts_utc")
    precheck_degraded = True
else:
    try:
        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age_sec = (datetime.now(timezone.utc) - ts_dt).total_seconds()
        if age_sec > ttl_sec:
            warn(f"SESSION_STATE stale ({int(age_sec)}s > {ttl_sec}s); continuing in degraded mode")
            precheck_errors.append("SESSION_STATE stale")
            precheck_degraded = True
    except Exception:
        warn("SESSION_STATE ts_utc parse failed; continuing in degraded mode")
        precheck_errors.append("SESSION_STATE ts_utc parse failed")
        precheck_degraded = True

OUT_DIR.mkdir(parents=True, exist_ok=True)

fallback_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
trace_id = state.get("trace_id") or f"trace-degraded-{fallback_ts}"
task_id = state.get("task_id")
# Debug Trace
print(f"[LIAM] Env Keys: {list(os.environ.keys())}")
if "LUKA_ARGS_JSON" in os.environ:
    print(f"[LIAM] LUKA_ARGS_JSON found: {os.environ['LUKA_ARGS_JSON']}")
else:
    print(f"[LIAM] LUKA_ARGS_JSON NOT found")

goal = state.get("goal", "UNSPECIFIED")

# Phase 2.1: Dynamic Goal Override (Bridge)
sys.path.append(str(ROOT))
try:
    from observability.tools.memory import task_artifacts
except Exception:
    task_artifacts = None
try:
    luka_args = os.environ.get("LUKA_ARGS_JSON")
    if luka_args:
        args = json.loads(luka_args)
        if args.get("goal"):
            goal = args.get("goal")
            print(f"[LIAM] Goal overridden by Bridge: {goal}")
        if args.get("task_id"):
            task_id = str(args.get("task_id"))
        if args.get("trace_id"):
            trace_id = str(args.get("trace_id"))
except Exception as e:
    print(f"[LIAM] Failed to parse LUKA_ARGS_JSON: {e}")

if task_artifacts:
    trace_id = task_artifacts.ensure_trace_id(task_id, trace_id)

plan = {
    "trace_id": trace_id,
    "intent": "plan",
    "level": "L2",
    "goal": goal,
    "precheck": {
        "status": "degraded" if precheck_degraded else "ok",
        "errors": precheck_errors,
        "ttl_sec": ttl_sec,
        "ts_utc": ts,
    },
    "source": {
        "session_json": str(SESSION_JSON),
        "session_md": str(SESSION_MD) if SESSION_MD.exists() else None
    },
    "assumptions": [],
    "constraints": ["NO_GIT", "DISPATCH_ONLY"],
    "subtasks": [
        {
            "id": "exec-1",
            "executor": "lisa",
            "intent": "execute",
            "description": f"Execute goal: {goal}",
            "success_criteria": ["execution complete"]
        }
    ],
    "success_criteria": ["all subtasks dispatched"],
    "created_utc": datetime.now(timezone.utc).isoformat()
}

try:
    telemetry_payload = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "module": "liam_planner",
        "status": "degraded" if precheck_degraded else "ok",
        "precheck": plan["precheck"],
        "trace_id": trace_id,
        "task_id": task_id,
        "goal": goal,
    }
    write_json(TELEMETRY_PATH, telemetry_payload)
except Exception as e:
    warn(f"Telemetry write failed: {e}")

out = OUT_DIR / f"{trace_id}.plan.json"
try:
    out.write_text(json.dumps(plan, indent=2))
    print(f"[LIAM] Plan written: {out}")
except Exception as e:
    fail(f"Write failed: {e}")

if task_artifacts:
    plan["trace_id"] = trace_id
    try:
        task_artifacts.write_plan_artifacts(
            ROOT,
            trace_id=trace_id,
            task_id=task_id,
            agent_id="liam",
            goal=goal,
            plan=plan,
        )
    except Exception as e:
        print(f"[LIAM] Plan artifact failed: {e}", file=sys.stderr)
