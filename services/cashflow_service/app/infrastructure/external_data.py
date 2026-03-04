"""External data adapters with Circuit Breaker pattern.

Provides weather (IMD/OpenWeather) and market price (agmarknet) adapters
that degrade gracefully when external APIs are unavailable.

Circuit Breaker states:
- CLOSED: normal operation, requests go through
- OPEN: too many failures, return fallback immediately
- HALF_OPEN: after cooldown, allow one test request
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for external API calls."""
    name: str
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0
    _failure_count: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and time.monotonic() - self._last_failure_time >= self.recovery_timeout_seconds:
            self._state = CircuitState.HALF_OPEN
            logger.info("Circuit %s → HALF_OPEN (recovery timeout elapsed)", self.name)
        return self._state

    def record_success(self) -> None:
        if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit %s → OPEN after %d failures",
                self.name, self._failure_count,
            )

    def is_call_permitted(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


# ---------------------------------------------------------------------------
# Weather Data Adapter (OpenWeather / IMD)
# ---------------------------------------------------------------------------
class HttpWeatherDataProvider:
    """Fetches weather impact data from OpenWeather API.

    Falls back to a neutral adjustment (1.0) when the API is unavailable.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openweathermap.org/data/2.5",
        timeout: float = 10.0,
        verify_ssl: bool = True,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._circuit = CircuitBreaker(name="weather-api", failure_threshold=3, recovery_timeout_seconds=120)

    async def get_weather_adjustment(self, district: str, season: str) -> float:
        """Return a weather-based adjustment factor.

        Falls back to 1.0 (neutral) if the API is unavailable.
        """
        if not self._api_key:
            logger.debug("No weather API key configured; returning neutral adjustment")
            return 1.0

        if not self._circuit.is_call_permitted():
            logger.info("Weather circuit OPEN; returning fallback 1.0")
            return 1.0

        try:
            async with httpx.AsyncClient(timeout=self._timeout, verify=self._verify_ssl) as client:
                response = await client.get(
                    f"{self._base_url}/weather",
                    params={"q": f"{district},IN", "appid": self._api_key, "units": "metric"},
                )
                response.raise_for_status()
                data = response.json()

            self._circuit.record_success()

            # Derive adjustment from weather conditions
            return self._compute_adjustment(data, season)

        except (httpx.HTTPError, KeyError, ValueError) as exc:
            self._circuit.record_failure()
            logger.warning("Weather API call failed for %s: %s", district, exc)
            return 1.0

    def _compute_adjustment(self, data: dict[str, Any], season: str) -> float:
        """Derive a weather adjustment from API response.

        Heavy rain in Kharif = slight positive (normal monsoon).
        Drought conditions = negative (below 0.8).
        Extreme weather = negative.
        """
        main = data.get("weather", [{}])[0].get("main", "").lower()
        temp = data.get("main", {}).get("temp", 25.0)
        humidity = data.get("main", {}).get("humidity", 50)

        adjustment = 1.0

        # Extreme temperature penalty
        if temp > 45:
            adjustment -= 0.2
        elif temp > 40:
            adjustment -= 0.1

        # For Kharif, rain is good; drought is bad
        if season.upper() in ("KHARIF", "current"):
            if main in ("rain", "drizzle", "thunderstorm"):
                adjustment += 0.05
            elif main == "clear" and humidity < 30:
                adjustment -= 0.15  # drought risk

        # Extreme weather events
        if main in ("tornado", "squall"):
            adjustment -= 0.3

        return max(0.3, min(1.5, round(adjustment, 2)))


# ---------------------------------------------------------------------------
# Market Data Adapter — data.gov.in Agmarknet (Indian mandi prices)
# ---------------------------------------------------------------------------
# Agmarknet resource ID on data.gov.in:
_AGMARKNET_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
_AGMARKNET_BASE = "https://api.data.gov.in/resource"

# Approximate long-run MSP / average modal prices (INR/quintal) used as
# baseline when the live API returns no records for a commodity.
_BASELINE_MODAL_PRICES: dict[str, float] = {
    "rice": 2183,
    "wheat": 2275,
    "maize": 2090,
    "soybean": 4600,
    "cotton": 6620,
    "sugarcane": 315,
    "groundnut": 6377,
    "mustard": 5650,
    "tur": 7550,
    "moong": 8682,
    "urad": 7400,
}


class HttpMarketDataProvider:
    """Fetches Indian crop market prices from data.gov.in Agmarknet.

    Requires a free API key from https://data.gov.in — register there and
    find your key under "My Account → API Key".

    Falls back to 1.0 (neutral) when API is unavailable or returns no data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._circuit = CircuitBreaker(name="market-api", failure_threshold=3, recovery_timeout_seconds=120)

    async def get_market_adjustment(self, crop: str, district: str) -> float:
        """Return a market-price adjustment factor relative to MSP baseline.

        Queries data.gov.in Agmarknet for the latest modal mandi price for
        the given commodity in the given district.  Falls back to 1.0.
        """
        if not self._api_key:
            logger.debug("No MARKET_API_KEY configured; returning neutral adjustment")
            return 1.0

        if not self._circuit.is_call_permitted():
            logger.info("Market circuit OPEN; returning fallback 1.0")
            return 1.0

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{_AGMARKNET_BASE}/{_AGMARKNET_RESOURCE}",
                    params={
                        "api-key": self._api_key,
                        "format": "json",
                        "limit": "5",
                        "filters[commodity]": crop.lower(),
                        "filters[state]": "Gujarat",  # default state; real use passes region
                    },
                )
                response.raise_for_status()
                data = response.json()

            self._circuit.record_success()
            return self._compute_adjustment(data, crop)

        except (httpx.HTTPError, KeyError, ValueError) as exc:
            self._circuit.record_failure()
            logger.warning("Agmarknet API call failed for %s/%s: %s", crop, district, exc)
            return 1.0

    def _compute_adjustment(self, data: dict[str, Any], crop: str) -> float:
        """Derive price adjustment from data.gov.in response."""
        records: list[dict] = data.get("records", [])
        if not records:
            return 1.0

        # Parse modal prices and average them
        modal_prices: list[float] = []
        for rec in records:
            try:
                # API returns lowercase field names: modal_price
                price_val = rec.get("modal_price") or rec.get("Modal_Price") or 0
                modal_prices.append(float(price_val))
            except (TypeError, ValueError):
                continue

        if not modal_prices:
            return 1.0

        current_price = sum(modal_prices) / len(modal_prices)
        crop_key = crop.lower()
        baseline = _BASELINE_MODAL_PRICES.get(crop_key, 0)

        if baseline <= 0:
            logger.debug("No baseline price for %s; returning neutral", crop)
            return 1.0

        ratio = current_price / baseline
        adjustment = max(0.5, min(1.5, round(ratio, 2)))
        logger.info(
            "Market adjustment for %s: %.2f (current=%.0f, baseline=%.0f)",
            crop, adjustment, current_price, baseline,
        )
        return adjustment


# ---------------------------------------------------------------------------
# HTTP Data Providers for cross-service calls
# ---------------------------------------------------------------------------
class HttpProfileDataProvider:
    """Fetches profile data from the Profile Service via HTTP."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_profile_summary(self, profile_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/profiles/{profile_id}",
                )
                response.raise_for_status()
                data = response.json()
            return {
                "district": data.get("district", "unknown"),
                "primary_crop": data.get("primary_crop", "rice"),
                "occupation": data.get("occupation_type", "FARMER"),
                "household_monthly_expense": data.get("household_monthly_expense", 5000.0),
                "annual_income": data.get("annual_income", 100000.0),
            }
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Profile service call failed: %s", exc)
            return {
                "district": "unknown",
                "primary_crop": "rice",
                "occupation": "FARMER",
                "household_monthly_expense": 5000.0,
                "annual_income": 100000.0,
            }


class HttpLoanDataProvider:
    """Fetches loan obligation data from the Loan Tracker via HTTP."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_monthly_obligations(self, profile_id: str) -> float:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/loans/borrower/{profile_id}/exposure",
                    params={"annual_income": 100000},  # needed for DTI but we just want obligations
                )
                response.raise_for_status()
                data = response.json()
            return float(data.get("monthly_obligations", 0.0))
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Loan service call failed: %s", exc)
            return 0.0
