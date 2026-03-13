# Mac mini Supervisor Decision

Status: PROPOSED  
Scope: 0luka runtime host (Mac mini)

---

## Context

The Mac mini host runs multiple long-lived runtime services for the 0luka system, including:

- Antigravity backend (`control_tower.py`)
- Redis
- dispatcher / bridge workers
- mission / API services
- maintenance jobs

Two process supervision regimes currently coexist:

- launchd (macOS native supervisor)
- PM2 (Node ecosystem process manager)

This dual-supervisor situation creates ambiguity about host-level supervisor authority.

---

## Current Machine Truth

Verified runtime chain:

PM2
|-- Antigravity-HQ
|   `-- dotenvx
|       `-- python modules/antigravity/realtime/control_tower.py
|           `-- LISTEN :8089
|
`-- Antigravity-Monitor
    `-- dotenvx
        `-- python src/antigravity_prod.py

Additional host services are managed by launchd.

`com.antigravity.controltower` exists in launchd but is not the active live supervisor.

---

## Decision

launchd is the target host-level supervisor authority for the Mac mini host.

PM2 is recognized as the current live supervisor but not the intended long-term architecture.

This document does not define architecture ownership authority for runtime services.

---

## Supervisor Rule

Only one process supervisor should be active per host runtime service instance.

For the Mac mini host:

launchd = target host supervisor authority  
PM2 = tooling or development supervisor only

PM2 must not supervise host runtime services selected for launchd once migration completes.

---

## Rationale

### Native host lifecycle
launchd integrates with macOS boot, login, and session semantics.

### Deterministic ownership
A single host supervisor eliminates ambiguity in host process supervision.

### Failure domain clarity
launchd allows clearer separation between:

- host services
- runtime services
- tooling processes
- ad-hoc jobs

### Compatibility with 0luka architecture
0luka components (dispatcher, bridge, maintenance jobs) align better with launchd service management.

---

## Alternatives Considered

### PM2 as primary host supervisor

Advantages:
- convenient CLI (pm2 list, pm2 logs)
- easy environment injection with dotenvx
- simple grouping of runtime processes

Disadvantages:
- not native to macOS
- introduces an additional daemon layer
- increases risk of dual-supervisor drift
- weak host lifecycle integration

---

## Migration Strategy (non-executing plan)

### Phase 0 — Document current truth

Document PM2 as the current runtime supervisor.

No runtime changes.

---

### Phase 1 — Inventory PM2 processes

Classify each PM2 application:

- host runtime candidate
- legacy runtime
- tooling
- temporary debug process

---

### Phase 2 — Build launchd wrappers

Create launchd service definitions for host runtime services selected for launchd.

Environment injection continues via:

dotenvx run -- ./venv/bin/python3 modules/antigravity/realtime/control_tower.py

---

### Phase 3 — Shadow validation

Launch launchd-managed instances in validation mode.

Verify:

- environment correctness
- port ownership
- health endpoints
- restart behavior

---

### Phase 4 — Controlled cutover

Stop PM2 supervision of host runtime services selected for launchd.

Promote launchd supervision authority.

Verify:

- port bindings
- service health
- absence of duplicate runtimes

---

### Phase 5 — Legacy classification

Decide the fate of legacy services such as:

src/antigravity_prod.py

Possible outcomes:

- retirement
- manual debug tool
- monitored legacy runtime

---

## Risks

- environment injection differences between PM2 and launchd
- restart semantics change
- hidden PM2 dependencies
- legacy runtime interactions

---

## Verification Plan

Migration is considered successful when:

- selected host runtime services are supervised by launchd
- PM2 does not supervise production runtime services
- topology inventory confirms single supervisor ownership
- health checks pass for all runtime endpoints

---

## Evidence

Runtime topology evidence is documented in:

g/reports/mac-mini/runtime_topology.md

---

## Notes

PM2 may remain available for development workflows but must not supervise selected production host runtime services.
