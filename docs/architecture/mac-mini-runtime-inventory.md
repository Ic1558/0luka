# Mac mini Runtime Inventory (Architecture)

Status: DRAFT  
Scope: 0luka runtime host (Mac mini)  
Evidence source: PM2 inventory and runtime topology report

---

## Purpose

This document captures the current PM2-supervised runtime inventory and classifies each process for architectural decision-making.

It is not a replacement for runtime topology or evidence logs; it is the classification layer for supervisor decisions.

---

## Evidence Sources

- pm2 list
- pm2 info Antigravity-HQ
- pm2 info Antigravity-Monitor
- g/reports/mac-mini/runtime_topology.md

---

## PM2 Inventory (Current)

| PM2 App | Command | CWD | Classification |
|---|---|---|---|
| Antigravity-HQ | dotenvx → python modules/antigravity/realtime/control_tower.py | /Users/icmini/0luka/repos/option | canonical runtime (current live supervisor) |
| Antigravity-Monitor | dotenvx → python src/antigravity_prod.py | /Users/icmini/0luka/repos/option | legacy runtime (overlap) |
| OptionBugHunter | dotenvx → node src/live.js | /Users/icmini/0luka/repos/option | tooling / auxiliary runtime |

---

## Classification Notes

### Antigravity-HQ
- role: canonical backend runtime
- live supervisor: PM2
- target supervisor: launchd (decision document)

### Antigravity-Monitor
- role: legacy runtime path
- action: classify before retirement

### OptionBugHunter
- role: auxiliary tooling
- action: confirm whether it is part of canonical runtime or developer tooling

---

## Next Updates

- update classification after supervisor cutover decision
- re-run PM2 inventory if app list changes
- reconcile with launchd ownership changes when migration begins
