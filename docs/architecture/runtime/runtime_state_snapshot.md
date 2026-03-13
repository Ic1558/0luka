# Runtime State Snapshot (2026-03-13)

## Snapshot metadata

- Timestamp: 2026-03-13 18:35 +0700
- Workspace root: `/Users/icmini/0luka`
- Runtime working directory: `/Users/icmini/0luka/repos/option`

## Supervisor

- launchd label present: `com.antigravity.controltower`
- PM2 processes online: `Antigravity-HQ`, `Antigravity-Monitor`,
  `OptionBugHunter`

## Process state (Antigravity-HQ)

- Launcher PID: `97256`
- Python child PID: `97282`
- Process args:
  - launcher: `dotenvx run -- ./venv/bin/python3 modules/antigravity/realtime/control_tower.py`
  - child: `... Python ... modules/antigravity/realtime/control_tower.py`

## Entrypoint path

- Referenced by process: `modules/antigravity/realtime/control_tower.py`
- On-disk presence in `repos/option`: not found at snapshot time

## Port binding

- `8089` listening by PID `97282`

## API response sample

- `/api/status` returned JSON payload (runtime market/status object)
- `/api/contract` returned:
  `{"contract":"S50H26","sym":"S50H26.BK"}`

## Decision history file location

- `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`
- File exists at snapshot time
