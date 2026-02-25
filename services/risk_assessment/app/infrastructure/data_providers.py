"""Stub data providers for cross-service data access.

In production these make HTTP calls to Profile/Loan services.
For local dev and testing, they return configurable defaults.
"""

from __future__ import annotations

from services.shared.models import ProfileId


class StubProfileDataProvider:
    """In-memory / stub provider for testing and local dev."""

    def __init__(self, data: dict[str, dict] | None = None) -> None:
        self._volatility: dict[str, dict] = {}
        self._personal: dict[str, dict] = {}
        if data:
            for pid, d in data.items():
                self._volatility[pid] = d.get("volatility", {})
                self._personal[pid] = d.get("personal", {})

    def set_profile_data(
        self,
        profile_id: str,
        volatility: dict,
        personal: dict,
    ) -> None:
        self._volatility[profile_id] = volatility
        self._personal[profile_id] = personal

    async def get_income_volatility(self, profile_id: ProfileId) -> dict:
        return self._volatility.get(profile_id, {
            "coefficient_of_variation": 0.0,
            "annual_income": 100000,
            "months_below_average": 0,
            "seasonal_variance": 0.0,
        })

    async def get_personal_info(self, profile_id: ProfileId) -> dict:
        return self._personal.get(profile_id, {
            "age": 30,
            "dependents": 0,
            "has_irrigation": False,
            "crop_diversification_index": 0.5,
        })


class StubLoanDataProvider:
    """In-memory / stub provider for testing and local dev."""

    def __init__(self) -> None:
        self._exposure: dict[str, dict] = {}
        self._repayment: dict[str, dict] = {}

    def set_loan_data(
        self,
        profile_id: str,
        exposure: dict,
        repayment: dict,
    ) -> None:
        self._exposure[profile_id] = exposure
        self._repayment[profile_id] = repayment

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        return self._exposure.get(profile_id, {
            "debt_to_income_ratio": 0.0,
            "total_outstanding": 0.0,
            "active_loan_count": 0,
            "credit_utilisation": 0.0,
        })

    async def get_repayment_stats(self, profile_id: ProfileId) -> dict:
        return self._repayment.get(profile_id, {
            "on_time_ratio": 1.0,
            "has_defaults": False,
        })
