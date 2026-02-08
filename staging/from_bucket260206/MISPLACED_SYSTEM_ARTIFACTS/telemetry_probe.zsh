#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Users/icmini/0luka"
print "\n== Telemetry probe under: $ROOT ==\n"

# 1) Find telemetry-like directories
print "## Candidate directories"
find "$ROOT" -type d \( -iname 'telemetry' -o -iname 'observability' -o -iname 'reports' -o -iname 'health' -o -iname 'metrics' \) 2>/dev/null \
  | sed -n '1,200p'

# 2) Find newest json/jsonl under observability + g/reports (common in your earlier dumps)
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
