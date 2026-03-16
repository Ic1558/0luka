"""AG-63: Event bus schema policy."""
REQUIRED_FIELDS = ["trace_id", "entity_type", "entity_id", "actor", "phase", "severity", "payload"]
ALLOWED_SEVERITIES = ["INFO", "WARN", "ERROR", "CRITICAL"]
ALLOWED_ENTITY_TYPES = [
    "recommendation", "governance_record", "operator_decision", "chain_run",
    "policy", "learning_pattern", "inference_request", "agent_contract", "sovereign_session",
]
