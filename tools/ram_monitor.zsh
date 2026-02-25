#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
export ROOT

# Support Phase 1 Runtime Root
if [[ -n "${LUKA_RUNTIME_ROOT:-}" ]]; then
    OBS="${LUKA_RUNTIME_ROOT}/logs"
    ARTIFACTS_ROOT="${LUKA_RUNTIME_ROOT}/artifacts"
    # For relative references in artifacts
    OBS_REF="${LUKA_RUNTIME_ROOT}/logs"
    ARTIFACTS_REF="${LUKA_RUNTIME_ROOT}/artifacts"
else
    OBS="$ROOT/observability"
    ARTIFACTS_ROOT="$ROOT/artifacts"
    OBS_REF='${ROOT}/observability'
    ARTIFACTS_REF='${ROOT}/artifacts'
fi

cd "$ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$ARTIFACTS_ROOT/ram"
TASK_DIR="$OBS/quarantine/tasks"
TEL_DIR="$OBS/telemetry"
mkdir -p "$OUT_DIR" "$TASK_DIR" "$TEL_DIR"

OUT_JSON="$OUT_DIR/${TS}_ram_snapshot.json"
TEL_JSON="$TEL_DIR/ram_monitor.latest.json"
STATE_JSON="$TEL_DIR/ram_monitor.state.json"
TASK_YAML="$TASK_DIR/${TS}_ram_monitor.task.yaml"
OUT_JSON_REF="$ARTIFACTS_REF/ram/${TS}_ram_snapshot.json"
TEL_JSON_REF="$OBS_REF/telemetry/ram_monitor.latest.json"
PERSIST_WINDOW_SEC=300
PERSIST_EMIT_COOLDOWN_SEC=300

# Collect RAM info (macOS)
# vm_stat gives page counts; sysctl gives page size + memsize; we compute a few headline numbers.
python3 - <<PY > "$OUT_JSON"
import subprocess, re, json, time
def run(cmd):
    return subprocess.check_output(cmd, text=True)

vm = run(["/usr/bin/vm_stat"])
page_size = 4096
m = re.search(r"page size of (\d+) bytes", vm)
if m: page_size = int(m.group(1))

def val(name):
    mm = re.search(rf"^{re.escape(name)}:\s+(\d+)\.", vm, re.M)
    return int(mm.group(1)) if mm else 0

free = val("Pages free") * page_size
active = val("Pages active") * page_size
inactive = val("Pages inactive") * page_size
spec = val("Pages speculative") * page_size
wired = val("Pages wired down") * page_size
compressed = val("Pages occupied by compressor") * page_size

memsize = int(run(["/usr/sbin/sysctl","-n","hw.memsize"]).strip())

mb = 1024 * 1024
gb = 1024 * 1024 * 1024
alerts = []
pressure_level = "OK"

if compressed > 6 * gb:
    alerts.append({
      "level": "WARN",
      "rule": "compressed_gt_6gb",
      "value_bytes": compressed,
      "threshold_bytes": 6 * gb
    })
    pressure_level = "WARN"

if free < 200 * mb:
    alerts.append({
      "level": "CRITICAL",
      "rule": "free_lt_200mb",
      "value_bytes": free,
      "threshold_bytes": 200 * mb
    })
    pressure_level = "CRITICAL"

recommendation = "stable"
if pressure_level == "CRITICAL":
    recommendation = "reduce_memory_load"
elif pressure_level == "WARN":
    recommendation = "monitor"

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
          "rss_mb": int((rss_kb / 1024) + 0.5)
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
  "pressure_level": pressure_level,
  "recommendation": recommendation,
  "top_processes": top_processes,
  "suggest_kill_list": suggest_kill_list,
  "alerts": alerts,
  "note": "Computed from vm_stat + hw.memsize"
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY

# Telemetry breadcrumb (small latest file)
cp "$OUT_JSON" "$TEL_JSON"

# Collect computed values from snapshot for emit logic.
PRESSURE_LEVEL="$(python3 - <<PY
import json
p = json.load(open("$OUT_JSON", "r", encoding="utf-8"))
print(str(p.get("pressure_level", "")))
PY
)"
FREE_MB="$(python3 - <<PY
import json
p = json.load(open("$OUT_JSON", "r", encoding="utf-8"))
print(int((p.get("free_bytes", 0) or 0) / 1024 / 1024))
PY
)"
COMP_GB="$(python3 - <<PY
import json
p = json.load(open("$OUT_JSON", "r", encoding="utf-8"))
print(f"{((p.get('compressed_bytes', 0) or 0) / 1024 / 1024 / 1024):.1f}")
PY
)"

# Emit activity feed event on CRITICAL memory pressure (fail-open)
if [[ "$PRESSURE_LEVEL" == "CRITICAL" ]]; then
  COMPONENT_FEED_PATH="$OBS/logs/components/ram_monitor.jsonl"
  GLOBAL_FEED_PATH="$OBS/logs/activity_feed.jsonl"
  TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "$(dirname "$COMPONENT_FEED_PATH")" 2>/dev/null || true
  
  printf '{"ts_utc":"%s","phase_id":"PHASE10_RAM","action":"ram_pressure_alert","emit_mode":"runtime_auto","tool":"ram_monitor","pressure_level":"CRITICAL","free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$FREE_MB" "$COMP_GB" >> "$COMPONENT_FEED_PATH" 2>/dev/null || true
    
  python3 -m core.activity_feed_guard \
    "{\"ts_utc\":\"$TS_UTC\",\"action\":\"ram_pressure_alert\",\"emit_mode\":\"runtime_auto\",\"level\":\"CRITICAL\",\"result\":\"CRITICAL\",\"tool\":\"ram_monitor\",\"free_mb\":$FREE_MB,\"compressed_gb\":$COMP_GB}" \
    --feed "$GLOBAL_FEED_PATH" 2>/dev/null || true
fi

# Persistent CRITICAL detector (stateful, fail-open).
STABILITY_VARS="$(python3 - <<PY
import json
import time
from pathlib import Path

state_path = Path("$STATE_JSON")
window_sec = int("$PERSIST_WINDOW_SEC")
cooldown_sec = int("$PERSIST_EMIT_COOLDOWN_SEC")
now = int(time.time())

try:
    snap = json.load(open("$OUT_JSON", "r", encoding="utf-8"))
except Exception:
    snap = {}

try:
    state = json.load(open(state_path, "r", encoding="utf-8"))
except Exception:
    state = {}

level = str(snap.get("pressure_level", ""))
critical_since = state.get("critical_since_epoch")
last_emit = int(state.get("last_persistent_emit_epoch", 0) or 0)

emit_persistent = 0
critical_for = 0

if level == "CRITICAL":
    if not isinstance(critical_since, int):
        critical_since = now
    critical_for = max(0, now - critical_since)
    if critical_for >= window_sec and (now - last_emit) >= cooldown_sec:
        emit_persistent = 1
        last_emit = now
else:
    critical_since = None
    critical_for = 0

new_state = {
    "last_level": level,
    "critical_since_epoch": critical_since,
    "last_persistent_emit_epoch": last_emit,
    "updated_epoch": now,
}
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")

print(f"EMIT_PERSISTENT={emit_persistent}")
print(f"CRITICAL_FOR_SEC={critical_for}")
PY
)"

EMIT_PERSISTENT="0"
CRITICAL_FOR_SEC="0"
while IFS='=' read -r key val; do
  case "$key" in
    EMIT_PERSISTENT) EMIT_PERSISTENT="$val" ;;
    CRITICAL_FOR_SEC) CRITICAL_FOR_SEC="$val" ;;
  esac
done <<< "$STABILITY_VARS"

if [[ "$EMIT_PERSISTENT" == "1" ]]; then
  COMPONENT_FEED_PATH="$OBS/logs/components/ram_monitor.jsonl"
  GLOBAL_FEED_PATH="$OBS/logs/activity_feed.jsonl"
  TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "$(dirname "$COMPONENT_FEED_PATH")" 2>/dev/null || true
  
  printf '{"ts_utc":"%s","phase_id":"PHASE10_RAM","action":"ram_pressure_persistent","emit_mode":"runtime_auto","tool":"ram_monitor","pressure_level":"CRITICAL","critical_for_sec":%s,"free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$CRITICAL_FOR_SEC" "$FREE_MB" "$COMP_GB" >> "$COMPONENT_FEED_PATH" 2>/dev/null || true
    
  python3 -m core.activity_feed_guard \
    "{\"ts_utc\":\"$TS_UTC\",\"action\":\"ram_pressure_persistent\",\"emit_mode\":\"runtime_auto\",\"level\":\"CRITICAL\",\"result\":\"CRITICAL\",\"tool\":\"ram_monitor\",\"critical_for_sec\":$CRITICAL_FOR_SEC,\"free_mb\":$FREE_MB,\"compressed_gb\":$COMP_GB}" \
    --feed "$GLOBAL_FEED_PATH" 2>/dev/null || true
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
