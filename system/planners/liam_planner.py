#!/usr/bin/env python3
import json, sys, time, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path.home() / "0luka"
SESSION_JSON = ROOT / "g/session/session_state.latest.json"
SESSION_MD   = ROOT / "g/session/SESSION_STATE.md"
OUT_DIR     = ROOT / "interface/plans"

def fail(msg):
    print(f"[LIAM][FAIL] {msg}", file=sys.stderr)
    sys.exit(1)

# --- Session state (soft signal, warn-only) ---
state = {}
if SESSION_JSON.exists():
    try:
        state = json.loads(SESSION_JSON.read_text())
    except Exception:
        print("[LIAM][WARN] SESSION_STATE invalid JSON, continuing", file=sys.stderr)
else:
    print("[LIAM][WARN] SESSION_STATE missing, continuing", file=sys.stderr)

warn_state_stale = False
ts = state.get("ts_utc", "")
if not ts:
    warn_state_stale = True
    print("[LIAM][WARN] SESSION_STATE has no ts_utc", file=sys.stderr)

# --- Heartbeat gate (informational, not blocking) ---
HEARTBEAT = ROOT / "observability" / "artifacts" / "dispatcher_heartbeat.json"
_hb_ok = False
if HEARTBEAT.exists():
    try:
        hb = json.loads(HEARTBEAT.read_text())
        hb_pid = hb.get("pid")
        if hb_pid:
            os.kill(hb_pid, 0)  # check process alive
            _hb_ok = True
    except (ProcessLookupError, OSError):
        pass
    except Exception:
        pass

if not _hb_ok:
    print("[LIAM][WARN] Dispatcher heartbeat not live, plan will queue", file=sys.stderr)

OUT_DIR.mkdir(parents=True, exist_ok=True)

trace_id = state.get("trace_id", "trace-unknown")
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
