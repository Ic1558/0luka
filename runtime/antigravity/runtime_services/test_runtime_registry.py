"""Tests for Antigravity runtime service registry scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from runtime.antigravity.runtime_services.runtime_service_registry import (
    RuntimeServiceRegistry,
)


def _handler(_: object) -> object:
    return {"ok": True}


def test_register_and_get_service() -> None:
    registry = RuntimeServiceRegistry()
    registry.register_service("executor", _handler)
    assert registry.get_service("executor") is _handler


def test_registry_list_is_deterministic() -> None:
    registry = RuntimeServiceRegistry()
    registry.register_service("worker", _handler)
    registry.register_service("artifact_engine", _handler)
    registry.register_service("executor", _handler)
    assert registry.list_services() == ["artifact_engine", "executor", "worker"]


def test_unknown_service_returns_none() -> None:
    registry = RuntimeServiceRegistry()
    assert registry.get_service("missing") is None


def test_register_requires_valid_inputs() -> None:
    registry = RuntimeServiceRegistry()
    try:
        registry.register_service("", _handler)
    except ValueError as exc:
        assert str(exc) == "service_name_required"
    else:
        raise AssertionError("empty service name should fail")

    try:
        registry.register_service("bad", None)  # type: ignore[arg-type]
    except ValueError as exc:
        assert str(exc) == "service_handler_not_callable"
    else:
        raise AssertionError("non-callable handler should fail")
