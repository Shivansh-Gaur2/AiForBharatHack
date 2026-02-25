"""Stub data providers for local development and testing.

These return sensible defaults so the service can run without
cross-service HTTP calls.
"""

from __future__ import annotations

from services.shared.models import RiskCategory


class StubRiskDataProvider:
    """Returns configurable risk data for testing."""

    def __init__(
        self,
        risk_category: str = RiskCategory.MEDIUM,
        risk_score: float = 450.0,
    ) -> None:
        self._category = risk_category
        self._score = risk_score

    async def get_latest_risk_category(self, profile_id: str) -> str | None:
        return self._category

    async def get_risk_score(self, profile_id: str) -> float:
        return self._score


class StubCashFlowDataProvider:
    """Returns default cash flow projections for testing."""

    def __init__(
        self,
        projections: list[tuple[int, int, float, float]] | None = None,
        repayment_capacity: dict | None = None,
    ) -> None:
        self._projections = projections or [
            (1, 2026, 15000, 10000),
            (2, 2026, 12000, 10000),
            (3, 2026, 13000, 11000),
            (4, 2026, 30000, 12000),  # rabi harvest
            (5, 2026, 10000, 10000),
            (6, 2026, 8000, 13000),   # kharif inputs
            (7, 2026, 9000, 11000),
            (8, 2026, 10000, 10000),
            (9, 2026, 12000, 10000),
            (10, 2026, 45000, 12000), # kharif harvest
            (11, 2026, 20000, 11000),
            (12, 2026, 14000, 12000),
        ]
        self._capacity = repayment_capacity or {
            "recommended_emi": 3000,
            "max_affordable_emi": 5000,
            "monthly_surplus_avg": 7500,
            "emergency_reserve": 30000,
        }

    async def get_latest_forecast_projections(
        self, profile_id: str,
    ) -> list[tuple[int, int, float, float]]:
        return self._projections

    async def get_repayment_capacity(self, profile_id: str) -> dict:
        return self._capacity


class StubLoanDataProvider:
    """Returns default loan data for testing."""

    def __init__(
        self,
        exposure: dict | None = None,
        repayment_stats: dict | None = None,
    ) -> None:
        self._exposure = exposure or {
            "total_outstanding": 50000,
            "monthly_obligations": 4500,
            "debt_to_income_ratio": 0.25,
            "active_loan_count": 1,
        }
        self._repayment_stats = repayment_stats or {
            "missed_payments": 0,
            "days_overdue_avg": 0.0,
            "on_time_ratio": 1.0,
        }

    async def get_debt_exposure(self, profile_id: str) -> dict:
        return self._exposure

    async def get_repayment_stats(self, profile_id: str) -> dict:
        return self._repayment_stats


class StubProfileDataProvider:
    """Returns default profile data for testing."""

    def __init__(
        self,
        actual_incomes: list[tuple[int, int, float]] | None = None,
        household_expense: float = 8000.0,
    ) -> None:
        self._incomes = actual_incomes or [
            (1, 2026, 14000),
            (2, 2026, 11000),
            (3, 2026, 12000),
            (4, 2026, 28000),
            (5, 2026, 9000),
            (6, 2026, 7000),
        ]
        self._household_expense = household_expense

    async def get_actual_incomes(
        self, profile_id: str,
    ) -> list[tuple[int, int, float]]:
        return self._incomes

    async def get_household_expense(self, profile_id: str) -> float:
        return self._household_expense
