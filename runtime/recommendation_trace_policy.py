"""AG-59: Recommendation trace policy."""
REQUIRED_FIELDS = ["trace_id", "recommendation_id", "source_phase"]
OPTIONAL_FIELDS = ["governance_id", "decision_id", "memory_id", "audit_refs"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS + ["ts_created", "ts_updated"]
