#!/usr/bin/env python3
"""
Circuit Breaker pattern for protecting execution paths.

States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (probing)
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


class CircuitOpenError(RuntimeError):
    """Raised when a call is attempted on an open circuit."""
    pass


class CircuitBreaker:
    """Three-state circuit breaker with optional retry logic."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        *,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 60.0,
        max_retries: int = 0,
        backoff_factor: float = 1.5,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._total_calls = 0
        self._total_failures = 0

    @property
    def state(self) -> str:
        """Current state, accounting for recovery timeout."""
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout_sec:
                self._state = self.HALF_OPEN
        return self._state

    def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute fn through the circuit breaker.

        Raises CircuitOpenError if circuit is OPEN and recovery timeout hasn't elapsed.
        Retries up to max_retries on failure (with exponential backoff).
        """
        current_state = self.state

        if current_state == self.OPEN:
            raise CircuitOpenError(f"circuit '{self.name}' is OPEN")

        last_exc: Optional[Exception] = None
        attempts = 1 + self.max_retries

        for attempt in range(attempts):
            self._total_calls += 1
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get("status") == "error":
                    raise RuntimeError(f"error_result:{result.get('reason', 'unknown')}")
                self._failure_count = 0
                self._state = self.CLOSED
                return result
            except CircuitOpenError:
                raise
            except Exception as exc:
                last_exc = exc
                self._failure_count += 1
                self._total_failures += 1
                self._last_failure_time = time.monotonic()

                if self._failure_count >= self.failure_threshold:
                    self._state = self.OPEN

                if attempt < attempts - 1:
                    delay = self.backoff_factor * (2 ** attempt)
                    time.sleep(delay)

        raise last_exc  # type: ignore[misc]

    def reset(self) -> None:
        """Manual reset to CLOSED state."""
        self._state = self.CLOSED
        self._failure_count = 0

    def stats(self) -> dict:
        """Return current breaker statistics."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "recovery_timeout_sec": self.recovery_timeout_sec,
        }
