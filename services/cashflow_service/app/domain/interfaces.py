"""Domain interfaces (ports) for the Cash Flow service.

Following Ports & Adapters: the domain defines what it needs
and infrastructure provides concrete implementations.
"""

from __future__ import annotations

from typing import Protocol

from services.shared.models import ProfileId

from .models import CashFlowForecast, CashFlowRecord


class CashFlowRepository(Protocol):
    """Persistence port for cash-flow forecasts and records."""

    async def save_forecast(self, forecast: CashFlowForecast) -> None: ...

    async def find_forecast_by_id(self, forecast_id: str) -> CashFlowForecast | None: ...

    async def find_latest_forecast(self, profile_id: ProfileId) -> CashFlowForecast | None: ...

    async def find_forecast_history(
        self, profile_id: ProfileId, limit: int = 10,
    ) -> list[CashFlowForecast]: ...

    async def save_record(self, record: CashFlowRecord) -> None: ...

    async def save_records(self, records: list[CashFlowRecord]) -> None: ...

    async def find_records_by_profile(
        self, profile_id: ProfileId, limit: int = 200,
    ) -> list[CashFlowRecord]: ...


class WeatherDataProvider(Protocol):
    """Port for fetching weather/climate data (external adapter)."""

    async def get_weather_adjustment(
        self, district: str, season: str,
    ) -> float:
        """Return a multiplier (0.5–1.5) for weather impact on cash flow.

        1.0 = normal, <1.0 = adverse, >1.0 = favourable.
        """
        ...


class MarketDataProvider(Protocol):
    """Port for fetching crop/market price data (external adapter)."""

    async def get_market_adjustment(
        self, crop: str, district: str,
    ) -> float:
        """Return a multiplier for market-price impact on income.

        1.0 = normal, <1.0 = prices below normal, >1.0 = above normal.
        """
        ...


class ProfileDataProvider(Protocol):
    """Port for fetching profile data from the Profile Service."""

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        """Return district, occupation, crops, income info."""
        ...


class LoanDataProvider(Protocol):
    """Port for fetching loan obligation data from the Loan Tracker."""

    async def get_monthly_obligations(self, profile_id: ProfileId) -> float:
        """Return total monthly loan obligations for the borrower."""
        ...
