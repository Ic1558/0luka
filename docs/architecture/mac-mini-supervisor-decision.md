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

This dual-supervisor situation creates ambiguity about the authoritative runtime owner.

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

`com.antigravity.controltower` exists in launchd but is not the active runtime owner.

---

## Decision

launchd will be the canonical runtime supervisor for the Mac mini host.

PM2 is recognized as the current live supervisor but not the intended long-term architecture.

---

## Supervisor Rule

Only one process supervisor may own a canonical runtime service.

For the Mac mini host:

launchd = canonical supervisor  
PM2 = tooling or development supervisor only

PM2 must not supervise canonical runtime services once migration completes.

---

## Rationale

### Native host lifecycle
launchd integrates with macOS boot, login, and session semantics.

### Deterministic ownership
A single host supervisor eliminates ambiguity in runtime ownership.

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

### PM2 as canonical supervisor

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

- canonical runtime
- legacy runtime
- tooling
- temporary debug process

---

### Phase 2 — Build launchd wrappers

Create launchd service definitions for canonical runtime services.

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

Stop PM2 ownership of canonical runtime services.

Promote launchd ownership.

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

- canonical runtime services are owned by launchd
- PM2 does not supervise production runtime services
- topology inventory confirms single supervisor ownership
- health checks pass for all runtime endpoints

---

## Evidence

Runtime topology evidence is documented in:

g/reports/mac-mini/runtime_topology.md

---

## Notes

PM2 may remain available for development workflows but must not supervise canonical runtime services in production.
