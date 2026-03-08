"""HTTP-based data providers for cross-service communication.

These call the Profile and Loan Tracker services over HTTP to fetch
data needed for risk assessment.  Used in production; tests use stubs.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.shared.models import ProfileId

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0  # seconds


# ---------------------------------------------------------------------------
# Weather / Market risk provider (calls OpenWeather + Agmarknet directly)
# ---------------------------------------------------------------------------

_AGMARKNET_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
_AGMARKNET_BASE = "https://api.data.gov.in/resource"

# Approximate baseline MSP prices for ratio calculation
_BASELINE_MODAL_PRICES: dict[str, float] = {
    "rice": 2183, "wheat": 2275, "maize": 2090, "soybean": 4600,
    "cotton": 6620, "sugarcane": 315, "groundnut": 6377, "mustard": 5650,
    "tur": 7550, "moong": 8682, "urad": 7400,
}


class HttpWeatherMarketRiskProvider:
    """Fetches weather and market risk scores from external APIs.

    Weather risk score (0-100): derived from OpenWeather conditions.
      - 0 means no adverse weather, 100 means extreme weather risk.
    Market risk score (0-100): derived from Agmarknet mandi prices.
      - 0 means prices at/above MSP, 100 means prices far below MSP.
    """

    def __init__(
        self,
        weather_api_key: str | None = None,
        market_api_key: str | None = None,
    ) -> None:
        self._weather_key = weather_api_key
        self._market_key = market_api_key

    async def get_weather_risk(self, district: str) -> float:
        """Return weather risk score 0-100 for a district."""
        if not self._weather_key:
            logger.debug("No WEATHER_API_KEY; weather risk = 0 (no data)")
            return 0.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": f"{district},IN", "appid": self._weather_key, "units": "metric"},
                )
                r.raise_for_status()
                data = r.json()

            main_condition = data.get("weather", [{}])[0].get("main", "").lower()
            temp = data.get("main", {}).get("temp", 25.0)
            humidity = data.get("main", {}).get("humidity", 50)

            risk = 0.0
            if temp > 45:
                risk += 40
            elif temp > 40:
                risk += 20
            if main_condition in ("tornado", "squall"):
                risk += 60
            elif main_condition in ("thunderstorm",):
                risk += 15
            if humidity < 20:
                risk += 20  # severe drought risk
            elif humidity < 30:
                risk += 10

            return min(100.0, risk)
        except Exception as exc:
            logger.warning("Weather API failed for %s: %s", district, exc)
            return 0.0

    async def get_market_risk(self, crop: str, state: str) -> float:
        """Return market risk score 0-100 based on crop prices vs MSP."""
        if not self._market_key:
            logger.debug("No MARKET_API_KEY; market risk = 0 (no data)")
            return 0.0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{_AGMARKNET_BASE}/{_AGMARKNET_RESOURCE}",
                    params={
                        "api-key": self._market_key,
                        "format": "json",
                        "limit": "5",
                        "filters[commodity]": crop.lower(),
                        "filters[state]": state if state != "unknown" else "Gujarat",
                    },
                )
                r.raise_for_status()
                data = r.json()

            records = data.get("records", [])
            if not records:
                return 0.0

            prices = []
            for rec in records:
                try:
                    p = float(rec.get("modal_price") or rec.get("Modal_Price") or 0)
                    if p > 0:
                        prices.append(p)
                except (TypeError, ValueError):
                    continue

            if not prices:
                return 0.0

            avg_price = sum(prices) / len(prices)
            baseline = _BASELINE_MODAL_PRICES.get(crop.lower(), 0)
            if baseline <= 0:
                return 0.0

            # Price below MSP → market risk
            ratio = avg_price / baseline
            if ratio >= 1.0:
                return 0.0  # prices at or above MSP — no risk
            # Linear scaling: 50% below MSP → 100 risk
            return min(100.0, (1.0 - ratio) * 200)

        except Exception as exc:
            logger.warning("Agmarknet API failed for %s/%s: %s", crop, state, exc)
            return 0.0


class HttpProfileDataProvider:
    """Fetches profile data from the Profile Service via HTTP."""

    def __init__(self, base_url: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_income_volatility(self, profile_id: ProfileId) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/profiles/{profile_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # Extract volatility metrics from profile response
                volatility = data.get("volatility_metrics") or {}
                annual_income = data.get("estimated_annual_income", 0.0)
                return {
                    "coefficient_of_variation": volatility.get("coefficient_of_variation", 0.0),
                    "annual_income": annual_income,
                    "months_below_average": volatility.get("months_below_average", 0),
                    "seasonal_variance": volatility.get("seasonal_variance", 0.0),
                }
        except Exception:
            logger.exception("Failed to fetch profile volatility for %s", profile_id)
            return {
                "_error": True,
                "coefficient_of_variation": 0.0,
                "annual_income": 0.0,
                "months_below_average": 0,
                "seasonal_variance": 0.0,
            }

    async def get_personal_info(self, profile_id: ProfileId) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/profiles/{profile_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                personal = data.get("personal_info", {})
                livelihood = data.get("livelihood_info", {})
                crops = livelihood.get("crop_patterns", [])
                primary_crop = crops[0]["crop_name"] if crops else "unknown"

                return {
                    "age": personal.get("age", 0),
                    "dependents": personal.get("dependents", 0),
                    "has_irrigation": livelihood.get("has_irrigation", False),
                    "crop_diversification_index": livelihood.get(
                        "crop_diversification_index", 0.0
                    ),
                    "district": personal.get("district", "unknown"),
                    "state": personal.get("state", "unknown"),
                    "primary_crop": primary_crop,
                }
        except Exception:
            logger.exception("Failed to fetch personal info for %s", profile_id)
            return {
                "_error": True,
                "age": 0,
                "dependents": 0,
                "has_irrigation": False,
                "crop_diversification_index": 0.0,
                "district": "unknown",
                "state": "unknown",
                "primary_crop": "unknown",
            }


class HttpLoanDataProvider:
    """Fetches loan data from the Loan Tracker Service via HTTP."""

    def __init__(self, base_url: str, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/loans/borrower/{profile_id}/exposure"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                return {
                    "debt_to_income_ratio": data.get("debt_to_income_ratio", 0.0),
                    "total_outstanding": data.get("total_outstanding", 0.0),
                    "active_loan_count": data.get("active_loan_count", 0),
                    "credit_utilisation": data.get("credit_utilisation", 0.0),
                }
        except Exception:
            logger.exception("Failed to fetch debt exposure for %s", profile_id)
            return {
                "debt_to_income_ratio": 0.0,
                "total_outstanding": 0.0,
                "active_loan_count": 0,
                "credit_utilisation": 0.0,
            }

    async def get_repayment_stats(self, profile_id: ProfileId) -> dict[str, Any]:
        url = f"{self._base_url}/api/v1/loans/borrower/{profile_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                loans = resp.json().get("loans", [])

                if not loans:
                    return {"on_time_ratio": 0.0, "has_defaults": False, "_no_loans": True}

                total_repayments = 0
                on_time_count = 0
                has_defaults = False

                for loan in loans:
                    if loan.get("status") == "DEFAULTED":
                        has_defaults = True
                    for rep in loan.get("repayments", []):
                        total_repayments += 1
                        if rep.get("on_time", True):
                            on_time_count += 1

                on_time_ratio = (
                    on_time_count / total_repayments if total_repayments > 0 else 1.0
                )
                return {"on_time_ratio": on_time_ratio, "has_defaults": has_defaults}
        except Exception:
            logger.exception("Failed to fetch repayment stats for %s", profile_id)
            return {"on_time_ratio": 0.0, "has_defaults": False, "_error": True}
