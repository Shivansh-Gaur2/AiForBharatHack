"""HTTP-based cross-service data providers with circuit breakers.

Production adapters that call Risk, CashFlow, Loan, and Profile services.
"""

from __future__ import annotations

import logging

import httpx

from services.shared.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk Data Provider
# ---------------------------------------------------------------------------
class HttpRiskDataProvider:
    """Fetches risk data from the Risk Assessment service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(name="risk-service")

    async def get_latest_risk_category(self, profile_id: str) -> str | None:
        if not self._circuit.is_call_permitted():
            logger.warning("Circuit open for risk-service — returning None")
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/risk/profile/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return r.json().get("risk_category")
                if r.status_code == 404:
                    self._circuit.record_success()
                    return None
                self._circuit.record_failure()
                return None
        except Exception:
            logger.exception("Failed to fetch risk category")
            self._circuit.record_failure()
            return None

    async def get_risk_score(self, profile_id: str) -> float:
        if not self._circuit.is_call_permitted():
            return 500.0  # neutral default
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/risk/profile/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return float(r.json().get("risk_score", 500))
                self._circuit.record_failure()
                return 500.0
        except Exception:
            self._circuit.record_failure()
            return 500.0


# ---------------------------------------------------------------------------
# CashFlow Data Provider
# ---------------------------------------------------------------------------
class HttpCashFlowDataProvider:
    """Fetches cash flow data from the Cash Flow service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(name="cashflow-service")

    async def get_latest_forecast_projections(
        self, profile_id: str,
    ) -> list[tuple[int, int, float, float]]:
        if not self._circuit.is_call_permitted():
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/cashflow/forecast/profile/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    data = r.json()
                    return [
                        (p["month"], p["year"], p["projected_inflow"], p["projected_outflow"])
                        for p in data.get("monthly_projections", [])
                    ]
                self._circuit.record_failure()
                return []
        except Exception:
            self._circuit.record_failure()
            return []

    async def get_repayment_capacity(self, profile_id: str) -> dict:
        if not self._circuit.is_call_permitted():
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/cashflow/capacity/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return r.json()
                self._circuit.record_failure()
                return {}
        except Exception:
            self._circuit.record_failure()
            return {}


# ---------------------------------------------------------------------------
# Loan Data Provider
# ---------------------------------------------------------------------------
class HttpLoanDataProvider:
    """Fetches loan data from the Loan Tracker service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(name="loan-service")

    async def get_debt_exposure(self, profile_id: str) -> dict:
        if not self._circuit.is_call_permitted():
            return {"debt_to_income_ratio": 0, "monthly_obligations": 0}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/loans/borrower/{profile_id}/exposure")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return r.json()
                self._circuit.record_failure()
                return {"debt_to_income_ratio": 0, "monthly_obligations": 0}
        except Exception:
            self._circuit.record_failure()
            return {"debt_to_income_ratio": 0, "monthly_obligations": 0}

    async def get_repayment_stats(self, profile_id: str) -> dict:
        if not self._circuit.is_call_permitted():
            return {"missed_payments": 0, "days_overdue_avg": 0, "on_time_ratio": 1.0}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/loans/borrower/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    loans = r.json().get("items", [])
                    # Aggregate repayment stats from all loans
                    total_missed = 0
                    total_overdue_days = 0
                    total_repayments = 0
                    on_time_count = 0
                    for loan in loans:
                        for rep in loan.get("repayments", []):
                            total_repayments += 1
                            if rep.get("is_late"):
                                total_missed += 1
                                total_overdue_days += rep.get("days_overdue", 0)
                            else:
                                on_time_count += 1
                    avg_overdue = total_overdue_days / max(1, total_missed)
                    on_time_ratio = on_time_count / max(1, total_repayments)
                    return {
                        "missed_payments": total_missed,
                        "days_overdue_avg": avg_overdue,
                        "on_time_ratio": on_time_ratio,
                    }
                self._circuit.record_failure()
                return {"missed_payments": 0, "days_overdue_avg": 0, "on_time_ratio": 1.0}
        except Exception:
            self._circuit.record_failure()
            return {"missed_payments": 0, "days_overdue_avg": 0, "on_time_ratio": 1.0}


# ---------------------------------------------------------------------------
# Profile Data Provider
# ---------------------------------------------------------------------------
class HttpProfileDataProvider:
    """Fetches profile data from the Profile service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._circuit = CircuitBreaker(name="profile-service")

    async def get_actual_incomes(
        self, profile_id: str,
    ) -> list[tuple[int, int, float]]:
        # In production, this would call the profile service for income records
        # For now, return empty — the direct API bypasses this
        return []

    async def get_household_expense(self, profile_id: str) -> float:
        if not self._circuit.is_call_permitted():
            return 8000.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/profiles/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    data = r.json()
                    return float(data.get("monthly_household_expense", 8000))
                self._circuit.record_failure()
                return 8000.0
        except Exception:
            self._circuit.record_failure()
            return 8000.0

    async def get_phone_number(self, profile_id: str) -> str | None:
        if not self._circuit.is_call_permitted():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/profiles/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return r.json().get("phone")
                self._circuit.record_failure()
                return None
        except Exception:
            self._circuit.record_failure()
            return None

    async def get_preferred_language(self, profile_id: str) -> str:
        if not self._circuit.is_call_permitted():
            return "en"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/api/v1/profiles/{profile_id}")
                if r.status_code == 200:
                    self._circuit.record_success()
                    return r.json().get("preferred_language", "en")
                self._circuit.record_failure()
                return "en"
        except Exception:
            self._circuit.record_failure()
            return "en"
