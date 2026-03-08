"""HTTP adapters for cross-service data fetching with circuit breaker."""

from __future__ import annotations

import logging

import httpx

from services.shared.circuit_breaker import CircuitBreaker
from services.shared.models import ProfileId

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP Risk Data Provider
# ---------------------------------------------------------------------------


class HttpRiskDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker(name="risk-service")

    async def get_risk_category(self, profile_id: ProfileId) -> str:
        if not self._cb.is_call_permitted():
            return "UNKNOWN"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/risk/profile/{profile_id}/latest")
                r.raise_for_status()
                self._cb.record_success()
                return r.json().get("risk_category", "UNKNOWN")
        except Exception:
            self._cb.record_failure()
            logger.warning("Risk service unavailable, defaulting to UNKNOWN")
            return "UNKNOWN"

    async def get_risk_score(self, profile_id: ProfileId) -> float:
        if not self._cb.is_call_permitted():
            return 0.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/risk/profile/{profile_id}/latest")
                r.raise_for_status()
                self._cb.record_success()
                return float(r.json().get("risk_score", 0.0))
        except Exception:
            self._cb.record_failure()
            return 0.0


# ---------------------------------------------------------------------------
# HTTP CashFlow Data Provider
# ---------------------------------------------------------------------------


class HttpCashFlowDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker(name="cashflow-service")

    async def get_forecast_projections(
        self,
        profile_id: ProfileId,
    ) -> list[tuple[int, int, float, float]]:
        if not self._cb.is_call_permitted():
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/cashflow/forecast/profile/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                projections = r.json().get("monthly_projections", [])
                return [
                    (p["month"], p["year"], p["projected_inflow"], p["projected_outflow"])
                    for p in projections
                ]
        except Exception:
            self._cb.record_failure()
            return []

    async def get_repayment_capacity(self, profile_id: ProfileId) -> dict:
        if not self._cb.is_call_permitted():
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

    async def get_weather_market_context(self, profile_id: ProfileId) -> dict:
        """Fetch latest forecast assumptions and extract weather/market context for AI."""
        default = {"weather_condition": "normal", "market_condition": "normal"}
        if not self._cb.is_call_permitted():
            return default
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/cashflow/forecast/profile/{profile_id}")
                if r.status_code != 200:
                    return default
                self._cb.record_success()
                assumptions: list[dict] = r.json().get("assumptions", [])
                result = dict(default)
                for a in assumptions:
                    factor = a.get("factor", "").lower()
                    description = a.get("description", "normal")
                    if "weather" in factor:
                        result["weather_condition"] = description
                    elif "market" in factor or "price" in factor or "crop" in factor:
                        result["market_condition"] = description
                return result
        except Exception:
            self._cb.record_failure()
            return default


# ---------------------------------------------------------------------------
# HTTP Loan Data Provider
# ---------------------------------------------------------------------------


class HttpLoanDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker(name="loan-service")

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        if not self._cb.is_call_permitted():
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
        self._cb = CircuitBreaker(name="profile-service")

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        if not self._cb.is_call_permitted():
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
        if not self._cb.is_call_permitted():
            return 0.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base}/api/v1/profiles/{profile_id}")
                r.raise_for_status()
                self._cb.record_success()
                data = r.json()
                return float(data.get("average_monthly_expense", 0.0))
        except Exception:
            self._cb.record_failure()
            return 0.0


# ---------------------------------------------------------------------------
# HTTP Alert Data Provider
# ---------------------------------------------------------------------------


class HttpAlertDataProvider:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._cb = CircuitBreaker(name="early-warning-service")

    async def get_active_alerts(self, profile_id: ProfileId) -> list[dict]:
        if not self._cb.is_call_permitted():
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
