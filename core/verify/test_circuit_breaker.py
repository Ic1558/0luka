#!/usr/bin/env python3
"""Tests for circuit breaker module."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.circuit_breaker import CircuitBreaker, CircuitOpenError


def test_closed_on_success():
    """Circuit stays CLOSED on successful calls."""
    breaker = CircuitBreaker(name="test", failure_threshold=3, max_retries=0)
    result = breaker.call(lambda x: {"status": "ok", "data": x}, 42)
    assert result == {"status": "ok", "data": 42}
    assert breaker.state == CircuitBreaker.CLOSED
    assert breaker._failure_count == 0


def test_opens_after_threshold():
    """Circuit opens after failure_threshold consecutive failures."""
    call_count = 0

    def failing_fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("boom")

    breaker = CircuitBreaker(name="test", failure_threshold=3, max_retries=0, backoff_factor=0.01)

    for _ in range(3):
        try:
            breaker.call(failing_fn)
        except RuntimeError:
            pass

    assert breaker.state == CircuitBreaker.OPEN

    try:
        breaker.call(failing_fn)
        assert False, "should have raised CircuitOpenError"
    except CircuitOpenError:
        pass


def test_half_open_after_timeout():
    """Circuit transitions to HALF_OPEN after recovery timeout."""
    breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_sec=0.1, max_retries=0)

    try:
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    except RuntimeError:
        pass

    assert breaker.state == CircuitBreaker.OPEN
    time.sleep(0.15)
    assert breaker.state == CircuitBreaker.HALF_OPEN


def test_recovery_from_half_open():
    """Circuit recovers to CLOSED on success in HALF_OPEN state."""
    breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout_sec=0.1, max_retries=0)

    try:
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    except RuntimeError:
        pass

    time.sleep(0.15)
    assert breaker.state == CircuitBreaker.HALF_OPEN

    result = breaker.call(lambda: {"status": "ok"})
    assert result == {"status": "ok"}
    assert breaker.state == CircuitBreaker.CLOSED


def test_error_status_counts_as_failure():
    """A dict result with status=error is treated as a failure."""
    breaker = CircuitBreaker(name="test", failure_threshold=2, max_retries=0, backoff_factor=0.01)

    try:
        breaker.call(lambda: {"status": "error", "reason": "bad"})
    except RuntimeError:
        pass
    assert breaker._failure_count == 1


def test_reset():
    """Manual reset clears failure state."""
    breaker = CircuitBreaker(name="test", failure_threshold=1, max_retries=0)
    try:
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    except RuntimeError:
        pass
    assert breaker.state == CircuitBreaker.OPEN
    breaker.reset()
    assert breaker.state == CircuitBreaker.CLOSED
    assert breaker._failure_count == 0


def test_stats():
    """stats() returns current state info."""
    breaker = CircuitBreaker(name="mybreaker", failure_threshold=5)
    s = breaker.stats()
    assert s["name"] == "mybreaker"
    assert s["state"] == CircuitBreaker.CLOSED
    assert s["failure_threshold"] == 5


if __name__ == "__main__":
    test_closed_on_success()
    test_opens_after_threshold()
    test_half_open_after_timeout()
    test_recovery_from_half_open()
    test_error_status_counts_as_failure()
    test_reset()
    test_stats()
    print("test_circuit_breaker: 7/7 passed")
