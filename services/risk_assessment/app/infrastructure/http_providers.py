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
                volatility = data.get("volatility_metrics", {})
                return {
                    "coefficient_of_variation": volatility.get("coefficient_of_variation", 0.0),
                    "annual_income": volatility.get("annual_income", 100000),
                    "months_below_average": volatility.get("months_below_average", 0),
                    "seasonal_variance": volatility.get("seasonal_variance", 0.0),
                }
        except Exception:
            logger.exception("Failed to fetch profile volatility for %s", profile_id)
            return {
                "coefficient_of_variation": 0.0,
                "annual_income": 100000,
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
                return {
                    "age": personal.get("age", 30),
                    "dependents": personal.get("dependents", 0),
                    "has_irrigation": livelihood.get("has_irrigation", False),
                    "crop_diversification_index": livelihood.get(
                        "crop_diversification_index", 0.5
                    ),
                }
        except Exception:
            logger.exception("Failed to fetch personal info for %s", profile_id)
            return {
                "age": 30,
                "dependents": 0,
                "has_irrigation": False,
                "crop_diversification_index": 0.5,
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
                    return {"on_time_ratio": 1.0, "has_defaults": False}

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
            return {"on_time_ratio": 1.0, "has_defaults": False}
