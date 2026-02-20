# 0luka System Contract v1

Status: Constitutional Governance Contract (Binding)
Scope: Kernel v3 execution, evidence, and baseline integrity
Authority: Repository-enforced governance boundary

## 1) Purpose
This contract defines non-negotiable execution and evidence invariants for 0luka.
All operators, agents, and automation SHALL comply.

## 2) Control Plane Authority
Primary execution control SHALL be centralized in core/task_dispatcher.py.
No alternate dispatch loop SHALL bypass this control.
All task intake, dispatch outcomes, and lifecycle transitions SHALL pass through the canonical dispatcher path.

## 3) Dispatch and Runtime Invariants
Task ingestion SHALL be deterministic, auditable, and replay-safe.
Any malformed or invalid inbox payload SHALL be quarantined without crashing the watch loop.
Runtime failures SHALL degrade safely and preserve observability.

## 4) Activity Feed Integrity
The activity feed is an append-only operational ledger.
Events SHALL NOT be deleted or reordered.
Event emission SHALL preserve schema invariants required by feed linting and governance checks.
Any hygiene or rejection action SHALL include machine-parseable reason fields.

## 5) Baseline Integrity and Reproducibility
Baseline tags and boundary commits are constitutional anchors.
Baseline commit SHA MUST remain reproducible from repository history.
No governance operation SHALL rely on non-reproducible or private-only history states.

## 6) Change Constraints
Constitutional intent MUST be expressed with RFC-2119 terms (MUST/SHALL/MUST NOT).
Changes to execution authority, feed invariants, or baseline semantics SHALL require explicit governance review.
Unrelated runtime refactors SHALL NOT be bundled into governance contract changes.

## 7) Evidence Obligations
Each governance action SHALL produce a proof pack under observability/artifacts/proof_packs/.
Proof packs SHALL include command evidence, resulting SHAs, and deviation notes if any.
All claims of runtime health SHALL be backed by launchctl and linter evidence.

## 8) Violation Handling
On invariant breach, operations SHALL fail closed for governance state transitions.
Runtime operations MAY fail open only for telemetry append failures where safety is preserved.
All breaches SHALL be surfaced as explicit evidence for remediation.

## 9) Effective Boundary
This contract becomes active upon merge to main and remains active until superseded by a new approved contract version.
Conflicts with lower-order docs SHALL resolve in favor of this contract.
