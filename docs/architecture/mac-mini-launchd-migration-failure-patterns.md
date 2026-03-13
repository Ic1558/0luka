# PM2 → launchd Migration Failure Patterns (macOS)

## 1) Environment / venv resolution failures

Common causes:
- wrong PATH under launchd
- missing PYTHONPATH
- venv path drift
- dotenvx not found

Symptoms:
- launchd repeatedly respawns process
- errors only visible in stderr log

Preventive checks:
- verify wrapper PATH
- verify venv exists
- verify dotenvx absolute path

---

## 2) plist structure / permissions errors

Common causes:
- missing XML header
- invalid plist syntax
- wrapper not executable
- wrong file ownership

Symptoms:
- launchctl bootstrap failure
- service never appears in launchctl list

Preventive checks:
- plutil -lint
- verify wrapper path
- verify plist path

---

## 3) Port ownership conflicts

Common causes:
- PM2 service still bound to port
- stale process after crash
- shadow validation binding same port

Symptoms:
- launchd service starts then exits
- port already in use

Preventive checks:
- confirm port owner
- ensure PM2 runtime stopped before cutover
