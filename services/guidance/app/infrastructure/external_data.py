"""HTTP adapters for cross-service data fetching with circuit breaker."""

from __future__ import annotations

import logging
import time
from enum import StrEnum

import httpx

from services.shared.models import ProfileId

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker (shared across adapters)
# ---------------------------------------------------------------------------


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker opened after %d failures", self.failure_count)


# ---------------------------------------------------------------------------
# HTTP Risk Data Provider
# ---------------------------------------------------------------------------


class HttpRiskDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker()

    async def get_risk_category(self, profile_id: ProfileId) -> str:
        if not self._cb.can_execute():
            return "MEDIUM"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/risk/profile/{profile_id}/latest")
                r.raise_for_status()
                self._cb.record_success()
                return r.json().get("risk_category", "MEDIUM")
        except Exception:
            self._cb.record_failure()
            logger.warning("Risk service unavailable, defaulting to MEDIUM")
            return "MEDIUM"

    async def get_risk_score(self, profile_id: ProfileId) -> float:
        if not self._cb.can_execute():
            return 500.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/risk/profile/{profile_id}/latest")
                r.raise_for_status()
                self._cb.record_success()
                return float(r.json().get("risk_score", 500.0))
        except Exception:
            self._cb.record_failure()
            return 500.0


# ---------------------------------------------------------------------------
# HTTP CashFlow Data Provider
# ---------------------------------------------------------------------------


class HttpCashFlowDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker()

    async def get_forecast_projections(
        self,
        profile_id: ProfileId,
    ) -> list[tuple[int, int, float, float]]:
        if not self._cb.can_execute():
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/cashflow/forecast/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                projections = r.json().get("projections", [])
                return [
                    (p["month"], p["year"], p["inflow"], p["outflow"])
                    for p in projections
                ]
        except Exception:
            self._cb.record_failure()
            return []

    async def get_repayment_capacity(self, profile_id: ProfileId) -> dict:
        if not self._cb.can_execute():
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/cashflow/capacity/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                return r.json()
        except Exception:
            self._cb.record_failure()
            return {}


# ---------------------------------------------------------------------------
# HTTP Loan Data Provider
# ---------------------------------------------------------------------------


class HttpLoanDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker()

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        if not self._cb.can_execute():
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/loans/borrower/{profile_id}/exposure")
                r.raise_for_status()
                self._cb.record_success()
                return r.json()
        except Exception:
            self._cb.record_failure()
            return {}


# ---------------------------------------------------------------------------
# HTTP Profile Data Provider
# ---------------------------------------------------------------------------


class HttpProfileDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker()

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        if not self._cb.can_execute():
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/profiles/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                return r.json()
        except Exception:
            self._cb.record_failure()
            return {}

    async def get_household_expense(self, profile_id: ProfileId) -> float:
        if not self._cb.can_execute():
            return 8000.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/profiles/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                data = r.json()
                return float(data.get("household_monthly_expense", 8000.0))
        except Exception:
            self._cb.record_failure()
            return 8000.0


# ---------------------------------------------------------------------------
# HTTP Alert Data Provider
# ---------------------------------------------------------------------------


class HttpAlertDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker()

    async def get_active_alerts(self, profile_id: ProfileId) -> list[dict]:
        if not self._cb.can_execute():
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self._base}/api/v1/early-warning/alerts/profile/{profile_id}/active",
                )
                r.raise_for_status()
                self._cb.record_success()
                return r.json().get("items", [])
        except Exception:
            self._cb.record_failure()
            return []
