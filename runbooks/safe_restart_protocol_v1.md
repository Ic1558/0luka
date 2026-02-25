# Safe Restart Protocol v1

Kernel-grade runbook for restarting services without introducing runtime drift.

## 0) Non-Negotiables

- Do not use bulk reload patterns such as `launchctl list | ... | xargs launchctl kickstart ...`.
- Do not remove `*_state.json` files without a deterministic `recovery_probe`.
- Restart one service at a time with proof after each step.
- Any restart or fix that touches runtime state resets the freeze baseline.

## 1) Preflight (Fail-Closed)

Run before any restart:

```bash
cd ~/0luka || exit 1

# 1) confirm runtime root
test -d /Users/icmini/0luka_runtime || { echo "missing runtime root"; exit 2; }

# 2) confirm feed path exists
test -f /Users/icmini/0luka_runtime/logs/activity_feed.jsonl || { echo "missing runtime feed"; exit 3; }

# 3) index health must be readable
cat /Users/icmini/0luka_runtime/logs/index/index_health.json | head -40 || exit 4
```

## 2) Single-Service Restart Pattern

Required sequence:

1. Prove service exists (service id + plist).
2. Restart via launchd for that service only.
3. Verify via `launchctl print` (state, paths, environment).
4. Verify feed or heartbeat evidence in expected window.

Example (`com.0luka.sovereign-loop`):

```bash
UID="$(id -u)"
SVC="com.0luka.sovereign-loop"

launchctl print "gui/${UID}/${SVC}" >/dev/null || { echo "service not registered: $SVC"; exit 10; }

launchctl kickstart -k "gui/${UID}/${SVC}" || { echo "kickstart failed: $SVC"; exit 11; }

launchctl print "gui/${UID}/${SVC}" | rg -n "state|path =|stdout path|stderr path|environment" -n
```

Pass criteria:

- `stdout` and `stderr` paths are under `/Users/icmini/0luka_runtime/logs/...`.
- `environment` includes `LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime`.

## 3) State File Rules (`activity_feed_state.json`)

- Do not remove and hope for opportunistic recreation.
- If regeneration is required:
  - emit exactly one deterministic `recovery_probe`,
  - then verify the state file is recreated.

Required proof:

```bash
ls -la /Users/icmini/0luka_runtime/activity_feed_state.json
tail -n 5 /Users/icmini/0luka_runtime/logs/activity_feed.jsonl | rg recovery_probe
```

## 4) Post-Check (Must Pass)

```bash
# no legacy redirects since restart
tail -n 400 /Users/icmini/0luka_runtime/logs/activity_feed.jsonl | rg "legacy_feed_path_redirected" && exit 20 || true

# no integrity risk
tail -n 400 /Users/icmini/0luka_runtime/logs/activity_feed.jsonl | rg "system_data_integrity_risk" && exit 21 || true

# index healthy
cat /Users/icmini/0luka_runtime/logs/index/index_health.json | rg '"status": "healthy"' || exit 22
```

## DoD (Safe Restart)

- No bulk reload used.
- Service restarted one-by-one with `launchctl print` proof.
- Runtime log paths confirmed.
- No `legacy_feed_path_redirected`.
- No `system_data_integrity_risk`.
- `index_health.status == "healthy"`.
