#!/usr/bin/env zsh
set -euo pipefail
export LC_ALL=en_US.UTF-8

ROOT="$HOME/0luka"
SNAP="$ROOT/interface/frontends/raycast/atg_multi_snap.zsh"
[[ -f "$SNAP" ]] || { echo "Missing: $SNAP"; exit 1; }

ts="$(date +%y%m%d_%H%M%S)"
cp -a "$SNAP" "$SNAP.bak.$ts"

python3 - <<'PY'
import pathlib, re

p = pathlib.Path.home() / "0luka/interface/frontends/raycast/atg_multi_snap.zsh"
txt = p.read_text(encoding="utf-8")

# 1) bump version string only if present
txt = txt.replace("v2.1\n", "v2.1.1\n")

# 2) replace _emit_file_block to be "missing" vs "error reading"
txt = re.sub(
r"""_emit_file_block$begin:math:text$$end:math:text$ \{.*?\n\}""",
r'''_emit_file_block() {
  local title="$1"
  local path="$2"
  local n="${3:-60}"
  echo "#### ${title}"
  echo '```'
  if [[ -f "$path" ]]; then
    tail -n "$n" "$path" 2>/dev/null || echo "(error reading: $path)"
  else
    echo "(missing: ${path#$HOME/})"
  fi
  echo '```'
  echo ""
}''',
txt,
flags=re.S
)

# 3) inject telemetry resolver helpers + update _key_telemetry
# find old _key_telemetry block and replace it
txt = re.sub(
r"""_key_telemetry$begin:math:text$$end:math:text$ \{.*?\n\}""",
r'''_resolve_first_existing() {
  # args: candidate paths...
  local c
  for c in "$@"; do
    [[ -f "$c" ]] && { echo "$c"; return 0; }
  done
  return 1
}

_key_telemetry() {
  local repo_path="$1"
  echo "## KEY TELEMETRY (latest only)"

  local health bridge ram
  health=$(_resolve_first_existing \
    "$repo_path/observability/telemetry/health.latest.json" \
    "$repo_path/g/telemetry/health.latest.json" \
    "$repo_path/telemetry/health.latest.json" \
  ) || health="$repo_path/observability/telemetry/health.latest.json"

  bridge=$(_resolve_first_existing \
    "$repo_path/observability/telemetry/bridge_consumer.latest.json" \
    "$repo_path/g/telemetry/bridge_consumer.latest.json" \
    "$repo_path/telemetry/bridge_consumer.latest.json" \
  ) || bridge="$repo_path/observability/telemetry/bridge_consumer.latest.json"

  ram=$(_resolve_first_existing \
    "$repo_path/observability/telemetry/ram_monitor.latest.json" \
    "$repo_path/g/telemetry/ram_monitor.latest.json" \
    "$repo_path/telemetry/ram_monitor.latest.json" \
  ) || ram="$repo_path/observability/telemetry/ram_monitor.latest.json"

  _emit_file_block "health.latest.json" "$health" 80
  _emit_file_block "bridge_consumer.latest.json" "$bridge" 80
  _emit_file_block "ram_monitor.latest.json" "$ram" 120
}''',
txt,
flags=re.S
)

# 4) ensure newline after git status code fence close
txt = txt.replace("echo '```'\n  fi\n  echo \"\"\n}", "echo '```'\n  fi\n  echo \"\" \n}")

p.write_text(txt, encoding="utf-8")
print("OK: patched atg_multi_snap.zsh -> v2.1.1 with telemetry fallback + markdown fix")
PY

chmod +x "$SNAP"
echo "Backup: $SNAP.bak.$ts"
echo "Run: $SNAP --copy >/dev/null ; pbpaste | head -n 8"
