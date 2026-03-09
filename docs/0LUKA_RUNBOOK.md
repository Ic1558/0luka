# 0LUKA Failure Runbook

**Operational Troubleshooting Manual**

---

## 1. Incident Classification

| Severity | Description | Action |
| :--- | :--- | :--- |
| **P0** | Runtime halted | Immediate restart |
| **P1** | Tasks blocked | Manual intervention |
| **P2** | Partial artifact failure | Debug handler |
| **P3** | UI / Mission Control issue | Non-critical |

---

## 2. Dispatcher Not Running
**Symptoms:** Tasks not moving, no new runs in Mission Control.
*   **Check:** `ps aux | grep task_dispatcher`
*   **Fix:** `cd ~/0luka && python3 core/task_dispatcher.py`
*   **Permanent fix:** `launchctl kickstart -k gui/$UID/com.0luka.dispatcher`

---

## 3. Task Stuck in Inbox
**Symptoms:** YAML file stays in `interface/inbox/`.
*   **Cause - Invalid Schema:** Check activity logs.
*   **Cause - Unknown job_type:** Router rejection.
*   **Cause - Approval Required:** Check for `pending approval` status.
*   **Debug:** `cat interface/inbox/<task>.yaml` or check `interface/rejected/`.

---

## 4. Approval Block
**Symptoms:** `execution_status = blocked`, `approval_state = pending`.
*   **Approve:** `python3 tools/ops/qs_approval_runtime.py approve <run_id>`
*   **Reject:** `python3 tools/ops/qs_approval_runtime.py reject <run_id>`

---

## 5. Artifact Missing
**Symptoms:** Run completed but artifact folder is empty.
*   **Debug:** `cat ~/0luka_runtime/state/qs_runs/<run_id>.json`
*   **Check Logs:** `tail -f ~/0luka_runtime/logs/activity_feed.jsonl`
*   **Cause:** Handler exception or artifact path misconfiguration.

---

## 6. Runtime State Corruption
**Symptoms:** Run JSON malformed, Mission Control failing.
*   **Step 1:** `pkill -f task_dispatcher`
*   **Step 2:** Restore from backup or remove corrupted run.
*   **Step 3:** `python3 core/task_dispatcher.py`

---

## 7. Mission Control Failure
**Symptoms:** `/api/qs_runs` returns error.
*   **Check:** `curl localhost:3100/health`
*   **Fix:** Restart the Mission Control server.

---

## 8. Emergency Recovery
If runtime is unstable:
1.  Stop system: `pkill -f task_dispatcher`
2.  Verify state: `ls ~/0luka_runtime/state/`
3.  Restart clean: `python3 core/task_dispatcher.py`
