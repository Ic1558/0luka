{
  "task_id": "TASK-20260130-173054-TEST001",
  "trace_id": "trace-TASK-20260130-173054-TEST001",
  "lane": "task",
  "intent": "Verify Task Lane V1 End-to-End",
  "origin": "test_runner",
  "executor": {
    "type": "test_lane",
    "target": "echo hello"
  },
  "inputs": {
    "foo": "bar"
  },
  "evidence_policy": {
    "emit": [
      "plan",
      "done"
    ]
  },
  "reply_policy": {
    "format": "markdown"
  }
}