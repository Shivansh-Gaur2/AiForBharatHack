"""Shared Circuit Breaker implementation.

Provides graceful degradation for external API calls across all services.

States:
- CLOSED: normal operation, all requests go through
- OPEN:   too many failures, return fallback immediately without calling
- HALF_OPEN: after cooldown period, allow one probe request through

Usage::

    cb = CircuitBreaker(name="weather-api", failure_threshold=3, recovery_timeout_seconds=60)

    async def call_external():
        if not cb.is_call_permitted():
            return fallback_value
        try:
            result = await real_call()
            cb.record_success()
            return result
        except Exception:
            cb.record_failure()
            return fallback_value
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for external API calls.

    Thread-unsafe — suitable for single-process async services.
    """

    name: str
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0
    _failure_count: int = field(default=0, init=False, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _last_failure_time: float = field(default=0.0, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info("Circuit %s → HALF_OPEN (recovery timeout elapsed)", self.name)
        return self._state

    def record_success(self) -> None:
        """Reset failure count and close the circuit on a successful call."""
        if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            if self._failure_count > 0:
                logger.info("Circuit %s → CLOSED", self.name)

    def record_failure(self) -> None:
        """Record a failure; open the circuit when threshold is reached."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit %s → OPEN after %d failures",
                self.name,
                self._failure_count,
            )

    def is_call_permitted(self) -> bool:
        """Return True if a call should be attempted."""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
