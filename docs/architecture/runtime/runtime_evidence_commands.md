# Runtime Evidence Commands (Antigravity)

This file lists the read-only commands used to capture runtime conformance
evidence on 2026-03-13.

## Commands

```sh
launchctl list | grep -i antigravity
pm2 list
pm2 show Antigravity-HQ
pm2 show Antigravity-Monitor
lsof -i :8089
curl -sS http://127.0.0.1:8089/api/status
curl -sS http://127.0.0.1:8089/api/contract
cd repos/option && pwd
cd repos/option && ls -l modules/antigravity/realtime/artifacts/hq_decision_history.jsonl
cd repos/option && test -f modules/antigravity/realtime/control_tower.py; echo $?
ps -p 97256 -o pid,ppid,comm,args
ps -p 97282 -o pid,ppid,comm,args
python3 -c "import ast; ast.parse(open('modules/antigravity/realtime/control_tower.py').read())"
```

## Notes

- Commands were used for evidence collection only.
- No runtime restart, service mutation, or configuration change was executed.
- The final `python3 -c` command failed because the referenced entrypoint file
  was not present on disk at verification time.
