"""
trace_versioning.py — Central version registry for the trace format.

To add future version support (e.g. v1.1):
  1. Add "1.1" to SUPPORTED_VERSIONS
  2. Implement _validate_v1_1(trace) and _migrate_v1_1(trace) functions
  3. Add an entry to _VERSION_HANDLERS:
       "1.1": {"version": "1.1", "validate": _validate_v1_1, "migrate": _migrate_v1_1}
"""

CURRENT_VERSION = "1.0"

SUPPORTED_VERSIONS = ["1.0"]

_REQUIRED_FIELDS_V1_0 = [
    "execution_mode",
    "normalized_task",
    "decision",
    "result",
]


def _validate_v1_0(trace: dict) -> list:
    """Returns list of missing required fields. Empty list = valid."""
    return [f for f in _REQUIRED_FIELDS_V1_0 if trace.get(f) is None]


def _migrate_v1_0(trace: dict) -> dict:
    """v1.0 is current — identity migration."""
    return trace


_VERSION_HANDLERS = {
    "1.0": {
        "version": "1.0",
        "validate": _validate_v1_0,
        "migrate": _migrate_v1_0,
    },
    # "1.1": {
    #     "version": "1.1",
    #     "validate": _validate_v1_1,
    #     "migrate": _migrate_v1_1,
    # },
}


def get_version_handler(version: str):
    """Returns handler dict for version, or None if unsupported."""
    if not isinstance(version, str):
        return None
    return _VERSION_HANDLERS.get(version)


def is_supported(version: str) -> bool:
    """Returns True if version is in SUPPORTED_VERSIONS."""
    if not isinstance(version, str):
        return False
    return version in SUPPORTED_VERSIONS
