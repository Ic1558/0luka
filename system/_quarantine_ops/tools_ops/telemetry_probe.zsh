#!/usr/bin/env zsh
# telemetry_probe.zsh — probe telemetry/observability directories for recent JSON/JSONL files
# Usage: ROOT=/path/to/0luka zsh tools/ops/telemetry_probe.zsh
# Lists candidate telemetry dirs + newest JSON files in each.
set -euo pipefail

ROOT="${ROOT:-/Users/icmini/0luka}"
print "\n== Telemetry probe under: $ROOT ==\n"

print "## Candidate directories"
find "$ROOT" -type d \( -iname 'telemetry' -o -iname 'observability' -o -iname 'reports' -o -iname 'health' -o -iname 'metrics' \) 2>/dev/null \
  | sed -n '1,200p'

print "\n## Newest JSON/JSONL in likely roots (top 30)"
for D in \
  "$ROOT/observability" \
  "$ROOT/g/reports" \
  "$ROOT/g/observability" \
  "$ROOT/system" \
  "$ROOT/runtime"
do
  [[ -d "$D" ]] || continue
  print "\n-- $D"
  find "$D" -type f \( -name "*.json" -o -name "*.jsonl" \) 2>/dev/null \
    -exec stat -f "%m %Sm %N" -t "%Y-%m-%d %H:%M:%S" {} \; \
    | sort -nr | head -n 30
done
