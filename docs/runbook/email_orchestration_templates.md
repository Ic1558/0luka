# Email orchestration templates (copy/paste)

1. `[LUKA][R0][CHECK] Daily health #health-001`\n```yaml
version: 1
task_id: health-001
ring: R0
lane: observe
steps:
  - summarize service heartbeat
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
2. `[LUKA][R1][EXEC] Build report #report-001`\n```yaml
version: 1
task_id: report-001
ring: R1
lane: assist
steps:
  - gather last 24h job status
  - write concise report
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
3. `[LUKA][R2][EXEC] Verification sweep #verify-001`\n```yaml
version: 1
task_id: verify-001
ring: R2
lane: execute
steps:
  - run pytest -q
  - run governance lock verify
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
4. `[LUKA][R2][EXEC] Redis bus check #redis-001`\n```yaml
version: 1
task_id: redis-001
ring: R2
lane: execute
steps:
  - publish probe payload
  - wait for response channel
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
5. `[LUKA][R2][EXEC] Doc update #doc-001`\n```yaml
version: 1
task_id: doc-001
ring: R2
steps:
  - update runbook section
  - commit with evidence refs
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
6. `[LUKA][R3][EXEC] Governed migration #gov-001`\n```yaml
version: 1
task_id: gov-001
ring: R3
lane: governed
steps:
  - apply migration plan from allowlist
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
7. `[LUKA][R1][EXEC] Numbered-list form #num-001`\n```yaml
version: 1
task_id: num-001
ring: R1
1. collect branch + head sha
2) summarize pending checks
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
8. `[LUKA][R0][CHECK] Inbox reconcile #mail-001`\n```yaml
version: 1
task_id: mail-001
ring: R0
steps:
  - list unseen count
  - record ingestion lag
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
9. `[LUKA][R2][EXEC] Launchd verify #launchd-001`\n```yaml
version: 1
task_id: launchd-001
ring: R2
steps:
  - check launchctl list
  - tail orchestrator logs
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
10. `[LUKA][R1][EXEC] Dry-run reply #reply-001`\n```yaml
version: 1
task_id: reply-001
ring: R1
steps:
  - run reply-test mode
  - attach report paths
auth.token: ${TOKEN}
reply: luka.ai@theedges.com
```
