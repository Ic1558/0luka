"""
skill_safety.py — Pre-execution safety gate for skill capabilities.
"""


def check_skill_safety(skill_id: str, capability: str, manifest: dict) -> dict:
    """
    Check whether a capability is safe to execute for the given skill.

    Rules:
      - capability must be in manifest["allowed_capabilities"]
      - capability must NOT be in manifest["forbidden_capabilities"]
      - if manifest is missing allowed_capabilities -> denied (undeclared_capability)
      - if capability not in allowed_capabilities -> denied (undeclared_capability)
      - if capability in forbidden_capabilities -> denied (forbidden_capability)

    Returns:
      {"allowed": bool, "reason": str}
    """
    if not isinstance(manifest, dict):
        return {"allowed": False, "reason": "undeclared_capability: manifest is not a dict"}

    allowed_caps = manifest.get("allowed_capabilities")
    forbidden_caps = manifest.get("forbidden_capabilities") or []

    # Missing allowed_capabilities declaration → fail closed
    if allowed_caps is None:
        return {
            "allowed": False,
            "reason": "undeclared_capability: manifest missing allowed_capabilities",
        }

    if not isinstance(allowed_caps, list):
        return {
            "allowed": False,
            "reason": "undeclared_capability: allowed_capabilities must be a list",
        }

    # Forbidden takes precedence
    if capability in forbidden_caps:
        return {
            "allowed": False,
            "reason": f"forbidden_capability: '{capability}' is explicitly forbidden for skill '{skill_id}'",
        }

    # Must be in allowed list
    if capability not in allowed_caps:
        return {
            "allowed": False,
            "reason": f"undeclared_capability: '{capability}' not in allowed_capabilities for skill '{skill_id}'",
        }

    return {
        "allowed": True,
        "reason": f"capability '{capability}' is allowed for skill '{skill_id}'",
    }
