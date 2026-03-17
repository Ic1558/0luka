"""In-memory runtime service registry scaffold for Antigravity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ServiceHandler = Callable[[Any], Any]


@dataclass
class RuntimeServiceRegistry:
    """Deterministic in-memory service registry."""

    _services: Dict[str, ServiceHandler] = field(default_factory=dict)

    def register_service(self, name: str, handler: ServiceHandler) -> None:
        normalized = str(name).strip()
        if not normalized:
            raise ValueError("service_name_required")
        if not callable(handler):
            raise ValueError("service_handler_not_callable")
        self._services[normalized] = handler

    def get_service(self, name: str) -> Optional[ServiceHandler]:
        return self._services.get(str(name).strip())

    def list_services(self) -> List[str]:
        return sorted(self._services.keys())


_REGISTRY = RuntimeServiceRegistry()


def register_service(name: str, handler: ServiceHandler) -> None:
    _REGISTRY.register_service(name, handler)


def get_service(name: str) -> Optional[ServiceHandler]:
    return _REGISTRY.get_service(name)


def list_services() -> List[str]:
    return _REGISTRY.list_services()
