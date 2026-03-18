_IMMUTABLE_PATHS = (".gemini/", "core/", "skills/")


def validate_execution(task: dict):
    """Guard 1: block writes to immutable paths."""
    if task.get("type") == "write":
        scope = task.get("scope", "")
        if any(p in scope for p in _IMMUTABLE_PATHS):
            return {
                "allowed": False,
                "reason": "IMMUTABLE_POLICY_VIOLATION",
            }
    return {"allowed": True}


def enforce_guard(command: dict, mode: str):
    """Guard 2: block plan_only execution + unknown commands."""

    # --- no execution in plan mode ---
    if mode == "plan_only":
        return {
            "allowed": False,
            "reason": "execution blocked in plan_only",
        }

    # --- deny unknown commands ---
    if command.get("source") == "proposed":
        return {
            "allowed": False,
            "reason": "unknown command",
        }

    return {
        "allowed": True,
    }
