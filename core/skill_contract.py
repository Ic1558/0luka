"""
skill_contract.py — Base contract for skill manifests and handlers.
"""

REQUIRED_MANIFEST_FIELDS = [
    "skill_id",
    "family",
    "description",
    "capabilities",
    "risk_tier",
    "input_schema",
]


def validate_manifest(manifest: dict) -> tuple:
    """
    Returns (valid: bool, reason: str).
    Checks all REQUIRED_MANIFEST_FIELDS are present and non-empty.
    """
    if not isinstance(manifest, dict):
        return False, "manifest must be a dict"

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest or manifest[field] is None:
            return False, f"manifest missing required field: '{field}'"

    if manifest.get("risk_tier") not in ("low", "medium", "high"):
        return False, f"manifest risk_tier must be low|medium|high, got: '{manifest.get('risk_tier')}'"

    if not isinstance(manifest.get("capabilities"), list) or len(manifest["capabilities"]) == 0:
        return False, "manifest 'capabilities' must be a non-empty list"

    return True, "ok"


def validate_handler(handler_module) -> tuple:
    """
    Returns (valid: bool, reason: str).
    Checks that handler_module has an execute() callable.
    """
    if handler_module is None:
        return False, "handler module is None"

    execute_fn = getattr(handler_module, "execute", None)
    if execute_fn is None:
        return False, "handler missing 'execute' function"

    if not callable(execute_fn):
        return False, "handler 'execute' is not callable"

    return True, "ok"
