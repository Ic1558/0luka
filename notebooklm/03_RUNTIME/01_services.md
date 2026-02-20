# Runtime Services (03_01)

## Active Agents

- **`com.0luka.dispatcher`**:
  - **Mode:** WATCH (`--watch`)
  - **Function:** Monitors `interface/inbox/` for new YAML commands.
  - **Heartbeat:** Emits activity feed entries every cycle.
- **`com.0luka.opal-api`**:
  - **Function:** Provides internal REST interface for tool interactions.
  - **Dependency:** `.venv/opal` (python-multipart).
- **`com.0luka.bridge_watchdog`**:
  - **Function:** Monitors dispatcher health and attempts restart on failure.

## Monitoring Endpoints

- **Activity Feed Linter:** `tools/ops/activity_feed_linter.py` (PASS - 0 violations)
- **Dispatcher Unit Test:** `core/verify/test_task_dispatcher.py` (**FAILING** - AssertionError in `test_dispatch_invalid_yaml_stays_in_inbox`)
- **Runtime Stats:** `observability/logs/worker.log`

---
*Note: Legacy kernel agents (`luka_kernel_d.py`) are retired.*
