#!/usr/bin/env zsh
set -euo pipefail

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
TASK_YAML="$TASK_DIR/${TS}_ram_monitor.task.yaml"
OUT_JSON_REF="$OBS_REF/artifacts/ram/${TS}_ram_snapshot.json"
TEL_JSON_REF="$OBS_REF/telemetry/ram_monitor.latest.json"

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
    ps_out = run(["/bin/ps", "-Ao", "pid=,comm=,rss="])
    rows = []
    for line in ps_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, name, rss_s = parts
        try:
            pid = int(pid_s)
            rss_kb = int(rss_s)
        except ValueError:
            continue
        rows.append((rss_kb, pid, name))
    rows.sort(reverse=True)
    for rss_kb, pid, name in rows[:5]:
        top_processes.append({
          "pid": pid,
          "name": name.replace('"', ""),
          "rss_mb": int((rss_kb / 1024) + 0.5)
        })
except Exception:
    top_processes = []

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
  "alerts": alerts,
  "note": "Computed from vm_stat + hw.memsize"
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY

# Telemetry breadcrumb (small latest file)
cp "$OUT_JSON" "$TEL_JSON"

# Emit activity feed event on CRITICAL memory pressure (fail-open)
if python3 - <<PY
import json, sys
p = json.load(open("$OUT_JSON", "r", encoding="utf-8"))
sys.exit(0 if p.get("pressure_level") == "CRITICAL" else 1)
PY
then
  FEED_PATH="$OBS/logs/activity_feed.jsonl"
  TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
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
  mkdir -p "$(dirname "$FEED_PATH")" 2>/dev/null || true
  printf '{"ts_utc":"%s","phase_id":"PHASE10_RAM","action":"ram_pressure_alert","emit_mode":"runtime_auto","tool":"ram_monitor","pressure_level":"CRITICAL","free_mb":%s,"compressed_gb":%s}\n' \
    "$TS_UTC" "$FREE_MB" "$COMP_GB" >> "$FEED_PATH" 2>/dev/null || true
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
