"""Stub data providers for local development and testing."""

from __future__ import annotations

from services.shared.models import ProfileId


class StubRiskDataProvider:
    """Returns reasonable defaults for risk data."""

    async def get_risk_category(self, profile_id: ProfileId) -> str:
        return "MEDIUM"

    async def get_risk_score(self, profile_id: ProfileId) -> float:
        return 450.0


class StubCashFlowDataProvider:
    """Returns 12-month seasonal cash flow projections."""

    async def get_forecast_projections(
        self,
        profile_id: ProfileId,
    ) -> list[tuple[int, int, float, float]]:
        # Seasonal pattern typical of a small farmer
        seasonal = {
            1: (12000, 8000),   # Rabi harvest
            2: (14000, 7500),
            3: (16000, 8000),   # Peak Rabi
            4: (8000, 7000),    # Low season
            5: (7000, 7500),
            6: (9000, 8000),    # Kharif sowing
            7: (10000, 9000),
            8: (11000, 8500),
            9: (13000, 8000),
            10: (15000, 8000),  # Kharif harvest
            11: (13000, 7500),
            12: (11000, 8000),
        }
        return [
            (month, 2026, inflow, outflow)
            for month, (inflow, outflow) in seasonal.items()
        ]

    async def get_repayment_capacity(self, profile_id: ProfileId) -> dict:
        return {
            "recommended_emi": 3500,
            "max_emi": 5000,
            "surplus_months": 9,
            "deficit_months": 3,
        }


class StubLoanDataProvider:
    """Returns reasonable defaults for loan exposure."""

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        return {
            "total_outstanding": 50000,
            "monthly_obligations": 4500,
            "dti_ratio": 0.32,
            "active_loan_count": 1,
        }


class StubProfileDataProvider:
    """Returns reasonable defaults for profile data."""

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        return {
            "occupation": "FARMER",
            "land_holding_acres": 2.5,
            "household_size": 5,
            "district": "Sample District",
        }

    async def get_household_expense(self, profile_id: ProfileId) -> float:
        return 8000.0


class StubAlertDataProvider:
    """Returns empty alerts list for stubs."""

    async def get_active_alerts(self, profile_id: ProfileId) -> list[dict]:
        return []


class StubAIProvider:
    """No-op AI provider used in local dev / tests."""

    async def generate_summary(self, context: dict) -> str | None:
        return None
