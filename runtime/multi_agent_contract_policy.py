"""AG-71: Multi-Agent Execution Contract policy."""

CONTRACT_VERSION = "1.0"

AUTHORITY_LEVELS = ["READ", "WRITE", "GOVERN", "SOVEREIGN"]
REQUIRED_TASK_FIELDS = ["task_id", "actor_id", "authority_level", "trace_id"]
REQUIRED_RESULT_FIELDS = ["task_id", "actor_id", "status", "trace_id"]
ALLOWED_STATUSES = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "REJECTED"]
