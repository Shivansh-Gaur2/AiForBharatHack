"""Stub data providers for cross-service data access.

In production these make HTTP calls to Profile/Loan services.
For local dev and testing, they return configurable defaults.
"""

from __future__ import annotations

from services.shared.models import ProfileId


class StubWeatherDataProvider:
    """In-memory stub for weather data (local dev / testing)."""

    def __init__(self, default_adjustment: float = 1.0) -> None:
        self._adjustments: dict[str, float] = {}
        self._default = default_adjustment

    def set_adjustment(self, district: str, season: str, value: float) -> None:
        self._adjustments[f"{district}:{season}"] = value

    async def get_weather_adjustment(self, district: str, season: str) -> float:
        return self._adjustments.get(f"{district}:{season}", self._default)


class StubMarketDataProvider:
    """In-memory stub for market price data (local dev / testing)."""

    def __init__(self, default_adjustment: float = 1.0) -> None:
        self._adjustments: dict[str, float] = {}
        self._default = default_adjustment

    def set_adjustment(self, crop: str, district: str, value: float) -> None:
        self._adjustments[f"{crop}:{district}"] = value

    async def get_market_adjustment(self, crop: str, district: str) -> float:
        return self._adjustments.get(f"{crop}:{district}", self._default)


class StubProfileDataProvider:
    """In-memory stub for profile data (local dev / testing)."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def set_profile_data(self, profile_id: str, data: dict) -> None:
        self._data[profile_id] = data

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        return self._data.get(profile_id, {
            "district": "unknown",
            "primary_crop": "rice",
            "occupation": "FARMER",
            "household_monthly_expense": 5000.0,
            "annual_income": 100000.0,
        })


class StubLoanDataProvider:
    """In-memory stub for loan obligation data (local dev / testing)."""

    def __init__(self) -> None:
        self._obligations: dict[str, float] = {}

    def set_monthly_obligations(self, profile_id: str, amount: float) -> None:
        self._obligations[profile_id] = amount

    async def get_monthly_obligations(self, profile_id: ProfileId) -> float:
        return self._obligations.get(profile_id, 0.0)
