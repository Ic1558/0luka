# 0LUKA Deployment Model

**Production Runtime Architecture**

---

## 1. Base Deployment
Single machine deployment (e.g., Mac mini).
*   **Components:** Dispatcher, Mission Control, Runtime State, Artifact Store.
*   **Architecture:** Dispatcher → Handlers → Artifacts (updates State Sidecar, projected to Mission Control).

---

## 2. launchd Service
The Dispatcher should run as a launch agent.

**Config:** `~/Library/LaunchAgents/com.0luka.dispatcher.plist`
```xml
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.0luka.dispatcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/icmini/0luka/core/task_dispatcher.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```
**Load:** `launchctl load ~/Library/LaunchAgents/com.0luka.dispatcher.plist`

---

## 3. Worker Scaling (Future)
*   **Current:** Single dispatcher, single worker.
*   **Future:** Dispatcher → Redis Queue → Multiple Workers (running domain handlers).

---

## 4. Artifact Storage Scaling
*   **Current:** Filesystem.
*   **Future:** S3 / GCS Object Storage (abstracted by storage layer).

---

## 5. Multi-Engine Architecture
Future modules (AEC, Finance, etc.) will all run through the standardized `run_registered_job()` interface.

---

## 6. Production Safety Model
*   Fail closed
*   Approval gate
*   Artifact immutability
*   Runtime state truth
