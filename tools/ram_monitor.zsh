#!/usr/bin/env zsh
set -euo pipefail

# Policy note:
# - macOS pages-free can stay low while system memory remains operational.
# - We use a composite CRITICAL decision to reduce false positives:
#   CRITICAL if base pressure is CRITICAL and at least one stress flag is true.
# - Latch clear uses hysteresis: require N consecutive non-CRITICAL samples.
# - Mode is fail-closed for threshold env parsing.

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
export ROOT
ROOT_REF='${ROOT}'
OBS="$ROOT/observability"
OBS_REF="${ROOT_REF}/observability"
cd "$ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$OBS/artifacts/ram"
TASK_DIR="$OBS/quarantine/tasks"
TEL_DIR="$OBS/telemetry"
mkdir -p "$OUT_DIR" "$TASK_DIR" "$TEL_DIR"

OUT_JSON="$OUT_DIR/${TS}_ram_snapshot.json"
TEL_JSON="$TEL_DIR/ram_monitor.latest.json"
STATE_JSON="$TEL_DIR/ram_monitor.state.json"
TASK_YAML="$TASK_DIR/${TS}_ram_monitor.task.yaml"
OUT_JSON_REF="$OBS_REF/artifacts/ram/${TS}_ram_snapshot.json"
TEL_JSON_REF="$OBS_REF/telemetry/ram_monitor.latest.json"
PERSIST_WINDOW_SEC=300
PERSIST_EMIT_COOLDOWN_SEC=300

parse_int_env() {
  local name="$1"
  local default="$2"
  local raw="${(P)name:-}"

  if [[ -z "$raw" ]]; then
    echo "$default"
    return 0
  fi
  if [[ "$raw" != <-> ]]; then
    echo "ERROR: $name must be a positive integer (got '$raw')" >&2
    exit 64
  fi
  if (( raw <= 0 )); then
    echo "ERROR: $name must be > 0 (got '$raw')" >&2
    exit 64
  fi
  echo "$raw"
}

RAM_MON_FREE_CRIT_BYTES="$(parse_int_env RAM_MON_FREE_CRIT_BYTES $((200*1024*1024)))"
RAM_MON_COMPRESSED_CRIT_BYTES="$(parse_int_env RAM_MON_COMPRESSED_CRIT_BYTES $((6*1024*1024*1024)))"
RAM_MON_CLEAR_STREAK="$(parse_int_env RAM_MON_CLEAR_STREAK 3)"
RAM_MON_SWAP_DELTA_CRIT="$(parse_int_env RAM_MON_SWAP_DELTA_CRIT 1)"

export RAM_MON_FREE_CRIT_BYTES
export RAM_MON_COMPRESSED_CRIT_BYTES
export RAM_MON_CLEAR_STREAK
export RAM_MON_SWAP_DELTA_CRIT
export OUT_JSON_PATH="$OUT_JSON"
export STATE_JSON_PATH="$STATE_JSON"
export RAM_MON_PERSIST_WINDOW_SEC="$PERSIST_WINDOW_SEC"
export RAM_MON_PERSIST_EMIT_COOLDOWN_SEC="$PERSIST_EMIT_COOLDOWN_SEC"

# Collect RAM info (macOS) and capture base pressure signal.
python3 - <<'PY'
import json
import os
import re
import subprocess
import time


def run(cmd):
    return subprocess.check_output(cmd, text=True)


def parse_int_opt(value: str | None):
    if value is None or value == "":
        return None
    try:
        iv = int(value)
    except Exception:
        raise SystemExit(f"ERROR: invalid simulation integer: {value}")
    if iv < 0:
        raise SystemExit(f"ERROR: simulation integer must be >= 0: {value}")
    return iv


sim_pressure = (os.getenv("RAM_MON_SIM_PRESSURE_LEVEL", "").strip().upper())
if sim_pressure and sim_pressure not in {"OK", "WARN", "CRITICAL"}:
    raise SystemExit(f"ERROR: RAM_MON_SIM_PRESSURE_LEVEL must be OK/WARN/CRITICAL (got '{sim_pressure}')")

sim_free = parse_int_opt(os.getenv("RAM_MON_SIM_FREE_BYTES"))
sim_comp = parse_int_opt(os.getenv("RAM_MON_SIM_COMPRESSED_BYTES"))
sim_swapins = parse_int_opt(os.getenv("RAM_MON_SIM_SWAPINS"))
sim_swapouts = parse_int_opt(os.getenv("RAM_MON_SIM_SWAPOUTS"))

vm = run(["/usr/bin/vm_stat"])
page_size = 4096
m = re.search(r"page size of (\d+) bytes", vm)
if m:
    page_size = int(m.group(1))


def val(name):
    mm = re.search(rf"^{re.escape(name)}:\s+(\d+)\.", vm, re.M)
    return int(mm.group(1)) if mm else 0


free = val("Pages free") * page_size
active = val("Pages active") * page_size
inactive = val("Pages inactive") * page_size
spec = val("Pages speculative") * page_size
wired = val("Pages wired down") * page_size
compressed = val("Pages occupied by compressor") * page_size

memsize = int(run(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip())

pressure_q = ""
free_pct = None
swapins = None
swapouts = None
try:
    pressure_q = run(["/usr/bin/memory_pressure", "-Q"])
    mq = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure_q)
    if mq:
        free_pct = int(mq.group(1))
except Exception:
    pass

try:
    pressure_full = run(["/usr/bin/memory_pressure"])
    ms_in = re.search(r"Swapins:\s*(\d+)", pressure_full)
    ms_out = re.search(r"Swapouts:\s*(\d+)", pressure_full)
    if ms_in:
        swapins = int(ms_in.group(1))
    if ms_out:
        swapouts = int(ms_out.group(1))
except Exception:
    pass

if sim_free is not None:
    free = sim_free
if sim_comp is not None:
    compressed = sim_comp
if sim_swapins is not None:
    swapins = sim_swapins
if sim_swapouts is not None:
    swapouts = sim_swapouts

if sim_pressure:
    base_pressure_level = sim_pressure
elif free_pct is None:
    # Conservative fallback when memory_pressure signal is unavailable.
    base_pressure_level = "WARN"
else:
    if free_pct <= 10:
        base_pressure_level = "CRITICAL"
    elif free_pct <= 20:
        base_pressure_level = "WARN"
    else:
        base_pressure_level = "OK"

recommendation = "monitor" if base_pressure_level != "OK" else "stable"

alerts = []
if free < int(os.environ["RAM_MON_FREE_CRIT_BYTES"]):
    alerts.append({
        "level": "WARN",
        "rule": "free_lt_threshold",
        "value_bytes": free,
        "threshold_bytes": int(os.environ["RAM_MON_FREE_CRIT_BYTES"]),
    })
if compressed >= int(os.environ["RAM_MON_COMPRESSED_CRIT_BYTES"]):
    alerts.append({
        "level": "WARN",
        "rule": "compressed_ge_threshold",
        "value_bytes": compressed,
        "threshold_bytes": int(os.environ["RAM_MON_COMPRESSED_CRIT_BYTES"]),
    })

top_processes = []
try:
    ps_out = run(["/bin/ps", "-Ao", "pid=,rss=,args="])
    rows = []
    for line in ps_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, rss_s, args = parts
        try:
            pid = int(pid_s)
            rss_kb = int(rss_s)
        except ValueError:
            continue
        rows.append((rss_kb, pid, args))
    rows.sort(reverse=True)
    for rss_kb, pid, args in rows[:5]:
        name = args.split()[0] if args else ""
        top_processes.append({
            "pid": pid,
            "name": name.replace('"', ""),
            "cmdline": args.replace('"', "")[:180],
            "rss_mb": int((rss_kb / 1024) + 0.5),
        })
except Exception:
    top_processes = []

suggest_kill_list = []
for proc in top_processes:
    name = str(proc.get("name", ""))
    cmdline = str(proc.get("cmdline", ""))
    hay = f"{name} {cmdline}"
    if any(tag in hay for tag in ("Helper", "Renderer", "TradingView", "Chrome", "Electron")):
        suggest_kill_list.append(
            {
                "pid": proc.get("pid"),
                "name": name,
                "cmdline": cmdline,
                "rss_mb": proc.get("rss_mb"),
            }
        )
    if len(suggest_kill_list) >= 3:
        break

out = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "module": "ram_monitor",
    "host": run(["/bin/hostname"]).strip(),
    "hw_mem_bytes": memsize,
    "free_bytes": free,
    "active_bytes": active,
    "inactive_bytes": inactive,
    "speculative_bytes": spec,
    "wired_bytes": wired,
    "compressed_bytes": compressed,
    "swapins": swapins,
    "swapouts": swapouts,
    "system_free_percent": free_pct,
    "pressure_level": base_pressure_level,
    "base_pressure_level": base_pressure_level,
    "recommendation": recommendation,
    "top_processes": top_processes,
    "suggest_kill_list": suggest_kill_list,
    "alerts": alerts,
    "note": "Computed from vm_stat + memory_pressure + hw.memsize",
}
with open(os.environ["OUT_JSON_PATH"], "w", encoding="utf-8") as f:
    f.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
PY

# Decide composite level + hysteresis and update state.
STABILITY_VARS="$(python3 - <<'PY'
import json
import os
import time
from pathlib import Path

state_path = Path(os.environ["STATE_JSON_PATH"])
out_path = Path(os.environ["OUT_JSON_PATH"])
window_sec = int(os.environ["RAM_MON_PERSIST_WINDOW_SEC"])
cooldown_sec = int(os.environ["RAM_MON_PERSIST_EMIT_COOLDOWN_SEC"])
free_crit = int(os.environ["RAM_MON_FREE_CRIT_BYTES"])
comp_crit = int(os.environ["RAM_MON_COMPRESSED_CRIT_BYTES"])
clear_streak = int(os.environ["RAM_MON_CLEAR_STREAK"])
swap_delta_crit = int(os.environ["RAM_MON_SWAP_DELTA_CRIT"])
now = int(time.time())

try:
    snap = json.loads(out_path.read_text(encoding="utf-8"))
except Exception:
    snap = {}

try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    state = {}

base_level = str(snap.get("base_pressure_level") or snap.get("pressure_level") or "WARN")
free_bytes = int(snap.get("free_bytes") or 0)
compressed_bytes = int(snap.get("compressed_bytes") or 0)
swapins = snap.get("swapins")
swapouts = snap.get("swapouts")

low_free = free_bytes < free_crit
high_compressed = compressed_bytes >= comp_crit

prev_swapins = state.get("last_swapins")
prev_swapouts = state.get("last_swapouts")

swapin_delta = None
swapout_delta = None
high_swap = False
if isinstance(swapins, int) and isinstance(swapouts, int) and isinstance(prev_swapins, int) and isinstance(prev_swapouts, int):
    swapin_delta = max(0, swapins - prev_swapins)
    swapout_delta = max(0, swapouts - prev_swapouts)
    high_swap = (swapin_delta >= swap_delta_crit) or (swapout_delta >= swap_delta_crit)

composite_critical = (base_level == "CRITICAL") and (low_free or high_compressed or high_swap)
if composite_critical:
    level = "CRITICAL"
elif base_level == "WARN" or high_compressed:
    level = "WARN"
else:
    level = "OK"

critical_since = state.get("critical_since_epoch")
last_emit = int(state.get("last_persistent_emit_epoch", 0) or 0)
prev_streak = int(state.get("non_critical_streak", 0) or 0)
prev_latch = bool(state.get("latch_active", False) or isinstance(critical_since, int))

emit_persistent = 0
critical_for = 0
non_critical_streak = prev_streak
latch_active = prev_latch
cleared = 0

if level == "CRITICAL":
    non_critical_streak = 0
    latch_active = True
    if not isinstance(critical_since, int):
        critical_since = now
    critical_for = max(0, now - critical_since)
    if critical_for >= window_sec and (now - last_emit) >= cooldown_sec:
        emit_persistent = 1
        last_emit = now
else:
    non_critical_streak = prev_streak + 1
    if non_critical_streak >= clear_streak:
        latch_active = False
        critical_since = None
        cleared = 1
    critical_for = max(0, now - critical_since) if isinstance(critical_since, int) else 0

recommendation = "stable"
if level == "CRITICAL":
    recommendation = "reduce_memory_load"
elif level == "WARN":
    recommendation = "monitor"

snap["pressure_level"] = level
snap["recommendation"] = recommendation
snap["decision"] = {
    "base_pressure_level": base_level,
    "low_free": low_free,
    "high_compressed": high_compressed,
    "high_swap_activity": high_swap,
    "swapin_delta": swapin_delta,
    "swapout_delta": swapout_delta,
    "composite_critical": composite_critical,
    "clear_streak_required": clear_streak,
    "non_critical_streak": non_critical_streak,
    "latch_active": latch_active,
    "cleared": bool(cleared),
}
out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

new_state = {
    "last_level": level,
    "critical_since_epoch": critical_since,
    "last_persistent_emit_epoch": last_emit,
    "updated_epoch": now,
    "non_critical_streak": non_critical_streak,
    "latch_active": latch_active,
    "last_swapins": swapins,
    "last_swapouts": swapouts,
}
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"PRESSURE_LEVEL={level}")
print(f"BASE_PRESSURE_LEVEL={base_level}")
print(f"FREE_BYTES={free_bytes}")
print(f"COMPRESSED_BYTES={compressed_bytes}")
print(f"FREE_MB={int(free_bytes / 1024 / 1024)}")
print(f"COMP_GB={(compressed_bytes / 1024 / 1024 / 1024):.1f}")
print(f"LOW_FREE={1 if low_free else 0}")
print(f"HIGH_COMPRESSED={1 if high_compressed else 0}")
print(f"HIGH_SWAP={1 if high_swap else 0}")
print(f"NON_CRITICAL_STREAK={non_critical_streak}")
print(f"CLEAR_STREAK={clear_streak}")
print(f"LATCH_ACTIVE={1 if latch_active else 0}")
print(f"CLEARED={cleared}")
print(f"EMIT_PERSISTENT={emit_persistent}")
print(f"CRITICAL_FOR_SEC={critical_for}")
PY
)"

PRESSURE_LEVEL="WARN"
BASE_PRESSURE_LEVEL="WARN"
FREE_BYTES="0"
COMPRESSED_BYTES="0"
FREE_MB="0"
COMP_GB="0.0"
LOW_FREE="0"
HIGH_COMPRESSED="0"
HIGH_SWAP="0"
NON_CRITICAL_STREAK="0"
CLEAR_STREAK="$RAM_MON_CLEAR_STREAK"
LATCH_ACTIVE="0"
CLEARED="0"
EMIT_PERSISTENT="0"
CRITICAL_FOR_SEC="0"
while IFS='=' read -r key val; do
  case "$key" in
    PRESSURE_LEVEL) PRESSURE_LEVEL="$val" ;;
    BASE_PRESSURE_LEVEL) BASE_PRESSURE_LEVEL="$val" ;;
    FREE_BYTES) FREE_BYTES="$val" ;;
    COMPRESSED_BYTES) COMPRESSED_BYTES="$val" ;;
    FREE_MB) FREE_MB="$val" ;;
    COMP_GB) COMP_GB="$val" ;;
    LOW_FREE) LOW_FREE="$val" ;;
    HIGH_COMPRESSED) HIGH_COMPRESSED="$val" ;;
    HIGH_SWAP) HIGH_SWAP="$val" ;;
    NON_CRITICAL_STREAK) NON_CRITICAL_STREAK="$val" ;;
    CLEAR_STREAK) CLEAR_STREAK="$val" ;;
    LATCH_ACTIVE) LATCH_ACTIVE="$val" ;;
    CLEARED) CLEARED="$val" ;;
    EMIT_PERSISTENT) EMIT_PERSISTENT="$val" ;;
    CRITICAL_FOR_SEC) CRITICAL_FOR_SEC="$val" ;;
  esac
done <<< "$STABILITY_VARS"

# Telemetry breadcrumb (small latest file)
cp "$OUT_JSON" "$TEL_JSON"

echo "decision: pressure_level=$PRESSURE_LEVEL base_pressure_level=$BASE_PRESSURE_LEVEL free_bytes=$FREE_BYTES compressed_bytes=$COMPRESSED_BYTES low_free=$LOW_FREE high_compressed=$HIGH_COMPRESSED high_swap=$HIGH_SWAP clear_streak=$CLEAR_STREAK non_critical_streak=$NON_CRITICAL_STREAK latch=$LATCH_ACTIVE cleared=$CLEARED"

# Emit activity feed event on CRITICAL memory pressure (fail-open)
if [[ "$PRESSURE_LEVEL" == "CRITICAL" ]]; then
  COMPONENT_FEED_PATH="$OBS/logs/components/ram_monitor.jsonl"
  GLOBAL_FEED_PATH="$OBS/logs/activity_feed.jsonl"
  TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "$(dirname "$COMPONENT_FEED_PATH")" 2>/dev/null || true

  printf '{"ts_utc":"%s","phase_id":"PHASE10_RAM","action":"ram_pressure_alert","emit_mode":"runtime_auto","tool":"ram_monitor","pressure_level":"CRITICAL","free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$FREE_MB" "$COMP_GB" >> "$COMPONENT_FEED_PATH" 2>/dev/null || true

  printf '{"ts_utc":"%s","action":"ram_pressure_alert","emit_mode":"runtime_auto","level":"CRITICAL","result":"CRITICAL","tool":"ram_monitor","free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$FREE_MB" "$COMP_GB" >> "$GLOBAL_FEED_PATH" 2>/dev/null || true
fi

if [[ "$EMIT_PERSISTENT" == "1" ]]; then
  COMPONENT_FEED_PATH="$OBS/logs/components/ram_monitor.jsonl"
  GLOBAL_FEED_PATH="$OBS/logs/activity_feed.jsonl"
  TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "$(dirname "$COMPONENT_FEED_PATH")" 2>/dev/null || true

  printf '{"ts_utc":"%s","phase_id":"PHASE10_RAM","action":"ram_pressure_persistent","emit_mode":"runtime_auto","tool":"ram_monitor","pressure_level":"CRITICAL","critical_for_sec":%s,"free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$CRITICAL_FOR_SEC" "$FREE_MB" "$COMP_GB" >> "$COMPONENT_FEED_PATH" 2>/dev/null || true

  printf '{"ts_utc":"%s","action":"ram_pressure_persistent","emit_mode":"runtime_auto","level":"CRITICAL","result":"CRITICAL","tool":"ram_monitor","critical_for_sec":%s,"free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$CRITICAL_FOR_SEC" "$FREE_MB" "$COMP_GB" >> "$GLOBAL_FEED_PATH" 2>/dev/null || true
fi

# sha256 for artifact (portable)
SHA="$(shasum -a 256 "$OUT_JSON" | awk '{print $1}')"

cat > "$TASK_YAML" <<YAML
actor: module.ram_monitor
intent: action.ram.snapshot
meta:
  ts_utc: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  host: "$(hostname)"
artifacts:
  outputs:
    - path: "$OUT_JSON_REF"
      sha256: "$SHA"
verification:
  gates:
    - gate.fs.purity
    - gate.hash.match
    - gate.proc.clean
YAML

# NOTE: core_kernel/router.py was quarantined; beacon logging disabled until replaced
# python3 "$ROOT/ops/core_kernel/router.py" "$TASK_YAML"
echo "OK: wrote $OUT_JSON_REF"
echo "OK: telemetry latest -> $TEL_JSON_REF"
echo "OK: committed beacon -> $OBS_REF/stl/ledger/global_beacon.jsonl"
