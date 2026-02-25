# Freeze T1 Monitoring (Lean)

Baseline-driven monitoring during the 12h freeze window.

## Baseline

Record once at freeze start:

```bash
BASE_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BASE_LINE="$(wc -l </Users/icmini/0luka_runtime/logs/activity_feed.jsonl | tr -d ' ')"
echo "BASE_TS=$BASE_TS"
echo "BASE_LINE=$BASE_LINE"
```

For the current freeze:

```bash
BASE_TS=2026-02-25T17:58:19Z
BASE_LINE=3146
```

## Every ~6 Hours

```bash
BASE_LINE=3146
tail -n +$((BASE_LINE+1)) /Users/icmini/0luka_runtime/logs/activity_feed.jsonl \
  | rg "system_data_integrity_risk|legacy_feed_path_redirected|rewrite_detected|index_stale|guard_violation" \
  || echo "T1_OK: no anomaly events since baseline"

cat /Users/icmini/0luka_runtime/logs/index/index_health.json | head -60
```

## Pass Criteria for Full 12h

- Zero anomaly events in the monitored set:
  - `system_data_integrity_risk`
  - `legacy_feed_path_redirected`
  - `rewrite_detected`
  - `index_stale`
  - `guard_violation`
- `index_health.status` remains `"healthy"` continuously.
- No forced regeneration of `activity_feed_state.json`.

## End-of-Freeze Proof

```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 core/health.py --full
tail -n 50 /Users/icmini/0luka_runtime/logs/activity_feed.jsonl | rg "system_data_integrity_risk|legacy_feed_path_redirected" || true
cat /Users/icmini/0luka_runtime/logs/index/index_health.json
```
