"""AG-29: Policy Effectiveness — public entry point.

Re-exports evaluate_policy_effectiveness() from effectiveness_store so
callers always import from a stable path:

    from core.policy.policy_effectiveness import evaluate_policy_effectiveness

Also provides the higher-level run_and_persist() for orchestration use.
"""
from core.policy.effectiveness_store import (  # noqa: F401
    evaluate_policy_effectiveness,
    run_and_persist,
    save_effectiveness,
    append_verification_log,
    get_effectiveness,
    list_effectiveness,
    list_verification_log,
)
