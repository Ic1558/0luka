# Mac mini Launchd Cutover Checklist

Status: DRAFT  
Scope: Antigravity control_tower launchd cutover (Mac mini)

---

## References

- docs/architecture/mac-mini-supervisor-decision.md
- docs/architecture/mac-mini-runtime-inventory.md
- g/reports/mac-mini/runtime_topology.md

---

## Pre-Cutover Verification (read-only)

- [ ] Wrapper exists: /Users/icmini/0luka/tools/ops/antigravity_controltower_wrapper.zsh
- [ ] dotenvx executable: /opt/homebrew/bin/dotenvx
- [ ] venv python: /Users/icmini/0luka/repos/option/venv/bin/python3
- [ ] log dir exists and writable: /Users/icmini/0luka/repos/option/artifacts
- [ ] plist draft validates: plutil -lint /Users/icmini/0luka/docs/architecture/drafts/com.antigravity.controltower.plist
- [ ] record current 8089 owner: lsof -nP -iTCP:8089 -sTCP:LISTEN
- [ ] PM2 state captured: pm2 list
- [ ] PM2 app details captured: pm2 info Antigravity-HQ

---

## Cutover

- [ ] copy plist draft to LaunchAgents:
      cp ~/0luka/docs/architecture/drafts/com.antigravity.controltower.plist \
         ~/Library/LaunchAgents/com.antigravity.controltower.plist
- [ ] re-lint in place: plutil -lint ~/Library/LaunchAgents/com.antigravity.controltower.plist
- [ ] bootout existing label (stops crash loop, unloads old plist): launchctl bootout gui/$(id -u)/com.antigravity.controltower
- [ ] stop PM2 owner: pm2 stop Antigravity-HQ
- [ ] bootstrap launchd: launchctl bootstrap gui/$(id -u) /Users/icmini/Library/LaunchAgents/com.antigravity.controltower.plist
- [ ] verify port 8089 owner: lsof -nP -iTCP:8089 -sTCP:LISTEN
- [ ] verify health endpoint: curl -fsS http://localhost:8089/api/status
- [ ] verify logs written:
  - /Users/icmini/0luka/repos/option/artifacts/launchd_controltower.out.log
  - /Users/icmini/0luka/repos/option/artifacts/launchd_controltower.err.log

---

## Rollback

- [ ] bootout launchd: launchctl bootout gui/$(id -u) /Users/icmini/Library/LaunchAgents/com.antigravity.controltower.plist
- [ ] restart PM2 owner: pm2 restart Antigravity-HQ
- [ ] confirm port 8089 owner: lsof -nP -iTCP:8089 -sTCP:LISTEN

---

## Notes

- Do not execute cutover steps until all pre-cutover items are satisfied.
- This checklist does not modify PM2 or launchd by itself; it only documents the sequence.
