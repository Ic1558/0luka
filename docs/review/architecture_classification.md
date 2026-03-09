1. WHAT THIS SYSTEM IS
This repository is a governance-first execution and control platform, not a single product application. The current codebase has a sealed submission path in [core/submit.py](/Users/icmini/0luka/core/submit.py), supervised dispatch in [core/task_dispatcher.py](/Users/icmini/0luka/core/task_dispatcher.py), bridge-based task adaptation in [core/bridge.py](/Users/icmini/0luka/core/bridge.py), and a read-only operator surface in [tools/ops/mission_control/server.py](/Users/icmini/0luka/tools/ops/mission_control/server.py). That makes the system best classified as a runtime/governance control plane with operator visibility and contract-based module integration.

2. WHAT THIS SYSTEM IS NOT
- It is not a simple end-user application centered on one business workflow.
- It is not only a macOS app. There may be local tooling and UI surfaces, but the architecture is built around queue submission, dispatch, policy gates, provenance, and read-only observability.
- It is not only a CLI wrapper around one module.
- It is not a standalone QS product yet.
- It is not a generic workflow board with no runtime law behind it.

3. DIFFERENCE FROM A NORMAL APP
A normal app is usually UI, API, business logic, and storage around one user-facing domain. This repo has those kinds of pieces, but it also has system-level layers that normal apps usually do not hard-code:
- sealed task envelopes and schema gates before inbox write in [core/submit.py](/Users/icmini/0luka/core/submit.py)
- a dispatcher loop with lifecycle events, provenance, and rejection handling in [core/task_dispatcher.py](/Users/icmini/0luka/core/task_dispatcher.py)
- bridge-based intent mapping in [core/bridge.py](/Users/icmini/0luka/core/bridge.py)
- Mission Control as an operator observability surface in [tools/ops/mission_control/server.py](/Users/icmini/0luka/tools/ops/mission_control/server.py)

That is why this is not just “an app on macOS.” The macOS-adjacent pieces are surfaces on top of a governed execution substrate.

4. DIFFERENCE FROM AN AUTOMATION TOOL
An automation tool mainly wires triggers to actions. This repo is stricter:
- submission is fail-closed on schema and hard-path violations in [core/submit.py](/Users/icmini/0luka/core/submit.py)
- dispatch is supervised and emits activity/provenance records in [core/task_dispatcher.py](/Users/icmini/0luka/core/task_dispatcher.py)
- operator access is intentionally read-only and constrained to observability paths in [tools/ops/mission_control/server.py](/Users/icmini/0luka/tools/ops/mission_control/server.py)
- domain modules are expected to integrate through explicit contracts rather than own their own runtime

That is closer to controlled execution infrastructure than to Zapier/n8n style flow wiring.

5. DIFFERENCE FROM AN AI AGENT FRAMEWORK
An AI agent framework usually emphasizes planning loops, tool calls, or multi-agent coordination. This repo is different in where the hard edges are:
- task ingress is governed by schema and envelope rules
- execution is routed through dispatcher and executor paths, not free-form loops
- observability and operator visibility are first-class
- module integration is explicit and bounded, shown by the bridge path into QS and the separate QS module surfaces in [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py)

So the center of gravity is runtime control and governance, not agent loop abstraction.

6. CURRENT ARCHITECTURAL LAYERS
- Governance and task ingress
  - [core/submit.py](/Users/icmini/0luka/core/submit.py)
- Dispatch and execution supervision
  - [core/task_dispatcher.py](/Users/icmini/0luka/core/task_dispatcher.py)
- Bridge and integration adaptation
  - [core/bridge.py](/Users/icmini/0luka/core/bridge.py)
- Operator visibility
  - [tools/ops/mission_control/server.py](/Users/icmini/0luka/tools/ops/mission_control/server.py)
- Domain module lane for QS
  - [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py)
  - [repos/qs/src/universal_qs_engine/contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/contracts.py)
  - [repos/qs/src/universal_qs_engine/artifacts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/artifacts.py)
  - [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py)

7. WHERE PRODUCT VALUE IS MISSING
The missing layer is a complete product application surface. The repo already has runtime law, dispatch, bridge integration, audit/provenance behavior, and operator visibility. What it does not yet have at the system level is a fully realized end-user product flow that hides those mechanics behind one domain-specific experience. That is why the system can feel indirect: the platform is more mature than the product layer sitting on it.

8. WHAT PRODUCT LAYER WOULD SIT ON TOP
The intended first product layer is `qs`. The evidence is already in-repo:
- bridge integration for QS exists in [core/bridge.py](/Users/icmini/0luka/core/bridge.py)
- QS has its own CLI and API-oriented domain surface in [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py)
- QS has domain data contracts in [repos/qs/src/universal_qs_engine/contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/contracts.py)
- QS has artifact export logic in [repos/qs/src/universal_qs_engine/artifacts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/artifacts.py)
- QS now has explicit product job contracts in [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py)

This means `qs` should sit above 0luka as the first real business application layer for BOQ, compliance, PO generation, and report export.

9. PRACTICAL CONSEQUENCES
Building the governed runtime first has clear consequences:
- It takes longer than building a normal app because submission, dispatch, provenance, and observability are built before a polished domain product.
- It is more reusable later because a product like `qs` can inherit queueing, control, and operator visibility instead of rebuilding them.
- It makes product work more disciplined because domain code must integrate through explicit contracts rather than bypass runtime rules.
- It also means the current user-facing value is incomplete until the `qs` layer is brought forward as the product surface.

10. FINAL CLASSIFICATION
Current system class: governance-first runtime and control platform with supervised dispatch and operator observability.
Current maturity: platform/runtime layers are real; product layer is only partially realized through the QS module lane.
Next logical move: continue building `qs` as the first product/application layer on top of sealed 0luka contracts.
