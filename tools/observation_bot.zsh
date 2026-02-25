#!/usr/bin/env zsh
# 0luka Observation Bot (read-only)
# Summarizes system health every 6 hours (manual trigger for this WO)

TS_FILE=$(date +%Y%m%d_%H%M)
OUTPUT="observability/artifacts/observation/${TS_FILE}.md"
FEED="observability/logs/activity_feed.jsonl"
INDEX="observability/logs/index/index_health.json"

echo "# 0luka Observation Report - $(date -u)" > $OUTPUT
echo "---" >> $OUTPUT

echo "## 1. Index Health" >> $OUTPUT
if [[ -f "$INDEX" ]]; then
  cat "$INDEX" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'- Status: {d.get(\"status\")}\n- Last Rebuild: {d.get(\"last_rebuild_ts\")}\n- Feed Size: {d.get(\"feed_size\")} bytes')" >> $OUTPUT
else
  echo "- Status: MISSING" >> $OUTPUT
fi

echo "\n## 2. Sovereign Control Plane" >> $OUTPUT
LAST_TICK=$(grep "sovereign_tick" "$FEED" | tail -n 1)
if [[ -n "$LAST_TICK" ]]; then
  echo "- Last Tick: $(echo $LAST_TICK | python3 -c 'import sys, json; print(json.load(sys.stdin).get("ts_utc"))')" >> $OUTPUT
else
  echo "- Last Tick: NONE FOUND" >> $OUTPUT
fi

RISK_COUNT=$(grep "system_data_integrity_risk" "$FEED" | wc -l | tr -d ' ')
echo "- Integrity Risks (24h): $RISK_COUNT" >> $OUTPUT

echo "\n## 3. Lifecycle & Resources" >> $OUTPUT
ROTATION_COUNT=$(grep -E "feed_rotated|rotation" "$FEED" | wc -l | tr -d ' ')
echo "- Rotation Events: $ROTATION_COUNT" >> $OUTPUT

# RAM Pressure Persistent Duration (last 24h)
# We look for the max critical_for_sec in the last sequence of ram_monitor logs
MAX_RAM_PRESSURE=$(grep "ram_pressure_persistent" "$FEED" | python3 -c "import sys, json; max_p=0; [max_p := max(max_p, json.loads(l).get('critical_for_sec', 0)) for l in sys.stdin]; print(max_p)")
echo "- Max Continuous RAM Pressure: ${MAX_RAM_PRESSURE}s" >> $OUTPUT

echo "\n## 4. Active Services (launchctl)" >> $OUTPUT
launchctl list | grep 0luka | awk '{print "- " $3 " (PID: " $1 ")"}' >> $OUTPUT

echo "\nReport generated at: $OUTPUT"
