"""Cross-service data aggregator.

Fetches borrower data from all micro-services (Profile, Risk, CashFlow,
Loan Tracker, Early Warning, Guidance) and assembles it into a unified
``BorrowerContext`` for the AI advisor's prompts.

Uses httpx with circuit-breaker pattern for resilience.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from services.shared.circuit_breaker import CircuitBreaker
from services.shared.models import ProfileId

from ..domain.models import BorrowerContext

logger = logging.getLogger(__name__)

# Default timeout for cross-service HTTP calls
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class HttpDataAggregator:
    """Aggregates borrower data from all micro-services over HTTP.

    Each service call is individually resilient — if one service is down,
    the aggregator still returns partial data from the rest.
    """

    def __init__(
        self,
        profile_url: str | None = None,
        risk_url: str | None = None,
        cashflow_url: str | None = None,
        loan_url: str | None = None,
        alert_url: str | None = None,
        guidance_url: str | None = None,
    ) -> None:
        self._profile_url = profile_url
        self._risk_url = risk_url
        self._cashflow_url = cashflow_url
        self._loan_url = loan_url
        self._alert_url = alert_url
        self._guidance_url = guidance_url

        # Per-service circuit breakers
        self._breakers = {
            "profile": CircuitBreaker(name="profile", failure_threshold=3, recovery_timeout_seconds=30),
            "risk": CircuitBreaker(name="risk", failure_threshold=3, recovery_timeout_seconds=30),
            "cashflow": CircuitBreaker(name="cashflow", failure_threshold=3, recovery_timeout_seconds=30),
            "loan": CircuitBreaker(name="loan", failure_threshold=3, recovery_timeout_seconds=30),
            "alert": CircuitBreaker(name="alert", failure_threshold=3, recovery_timeout_seconds=30),
            "guidance": CircuitBreaker(name="guidance", failure_threshold=3, recovery_timeout_seconds=30),
        }

    async def fetch_profile(self, profile_id: ProfileId) -> dict[str, Any]:
        if not self._profile_url:
            return {}
        return await self._safe_get(
            "profile",
            f"{self._profile_url}/api/v1/profiles/{profile_id}",
        )

    async def fetch_risk(self, profile_id: ProfileId) -> dict[str, Any]:
        if not self._risk_url:
            return {}
        return await self._safe_get(
            "risk",
            f"{self._risk_url}/api/v1/risk/profile/{profile_id}",
        )

    async def fetch_cashflow(self, profile_id: ProfileId) -> dict[str, Any]:
        if not self._cashflow_url:
            return {}

        # Fetch both forecast and capacity in parallel
        forecast, capacity = await asyncio.gather(
            self._safe_get(
                "cashflow",
                f"{self._cashflow_url}/api/v1/cashflow/forecast/profile/{profile_id}",
            ),
            self._safe_get(
                "cashflow",
                f"{self._cashflow_url}/api/v1/cashflow/capacity/{profile_id}",
            ),
            return_exceptions=True,
        )
        result: dict[str, Any] = {}
        if isinstance(forecast, dict):
            result["forecast"] = forecast
        if isinstance(capacity, dict):
            result["capacity"] = capacity
        return result

    async def fetch_loans(self, profile_id: ProfileId) -> dict[str, Any]:
        if not self._loan_url:
            return {}

        # Fetch loan list (exposure needs annual_income which we may not have yet)
        loans = await self._safe_get(
            "loan",
            f"{self._loan_url}/api/v1/loans/borrower/{profile_id}",
        )
        result: dict[str, Any] = {}
        if isinstance(loans, dict):
            result["loans"] = loans
        return result

    async def fetch_alerts(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        if not self._alert_url:
            return []
        data = await self._safe_get(
            "alert",
            f"{self._alert_url}/api/v1/early-warning/alerts/profile/{profile_id}/active",
        )
        if isinstance(data, dict):
            return data.get("alerts", [])
        return []

    async def fetch_guidance(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        if not self._guidance_url:
            return []
        data = await self._safe_get(
            "guidance",
            f"{self._guidance_url}/api/v1/guidance/profile/{profile_id}/active",
        )
        if isinstance(data, dict):
            return data.get("guidance_records", data.get("records", []))
        return []

    async def build_full_context(self, profile_id: ProfileId) -> BorrowerContext:
        """Fetch from all services in parallel and assemble a BorrowerContext."""
        context = BorrowerContext(profile_id=profile_id)

        # Fire all requests concurrently
        results = await asyncio.gather(
            self.fetch_profile(profile_id),
            self.fetch_risk(profile_id),
            self.fetch_cashflow(profile_id),
            self.fetch_loans(profile_id),
            self.fetch_alerts(profile_id),
            self.fetch_guidance(profile_id),
            return_exceptions=True,
        )

        # Unpack — each result is either data or an exception
        profile_data, risk_data, cashflow_data, loan_data, alert_data, guidance_data = results

        if isinstance(profile_data, dict) and profile_data:
            context.profile_summary = self._normalize_profile(profile_data)

        if isinstance(risk_data, dict) and risk_data:
            context.risk_assessment = risk_data

        if isinstance(cashflow_data, dict):
            forecast = cashflow_data.get("forecast", {})
            capacity = cashflow_data.get("capacity", {})
            if forecast:
                context.cashflow_forecast = self._normalize_forecast(forecast)
            if capacity:
                context.repayment_capacity = capacity

        if isinstance(loan_data, dict):
            loans = loan_data.get("loans", {})
            if isinstance(loans, dict):
                loan_items = loans.get("items", [])
                if loan_items:
                    context.active_loans = loan_items[:10]
                    # Build exposure summary from the loan list
                    total_outstanding = sum(l.get("outstanding_balance", 0) for l in loan_items)
                    monthly_obligations = sum(l.get("monthly_obligation", 0) for l in loan_items)
                    active_count = len([l for l in loan_items if l.get("status") == "ACTIVE"])
                    sources = list({l.get("source_type", "UNKNOWN") for l in loan_items})
                    context.loan_exposure = {
                        "total_outstanding": total_outstanding,
                        "monthly_obligations": monthly_obligations,
                        "active_loan_count": active_count,
                        "sources": [{"source_type": s} for s in sources],
                    }

        if isinstance(alert_data, list):
            context.active_alerts = alert_data[:5]

        if isinstance(guidance_data, list):
            context.active_guidance = guidance_data[:3]

        logger.info(
            "Built context for %s: has_data=%s",
            profile_id, context.has_data(),
        )
        return context

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _safe_get(self, service: str, url: str) -> dict[str, Any]:
        """HTTP GET with circuit breaker and error handling."""
        breaker = self._breakers.get(service)
        if breaker and not breaker.is_call_permitted():
            logger.debug("Circuit open for %s — skipping %s", service, url)
            return {}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    if breaker:
                        breaker.record_success()
                    return resp.json()
                elif resp.status_code == 404:
                    # Not found is not a failure — the profile might not exist yet
                    logger.debug("%s returned 404 for %s", service, url)
                    return {}
                else:
                    logger.warning(
                        "%s returned %d for %s", service, resp.status_code, url,
                    )
                    if breaker:
                        breaker.record_failure()
                    return {}
        except httpx.TimeoutException:
            logger.warning("Timeout calling %s: %s", service, url)
            if breaker:
                breaker.record_failure()
            return {}
        except Exception as exc:
            logger.warning("Error calling %s: %s — %s", service, url, exc)
            if breaker:
                breaker.record_failure()
            return {}

    def _normalize_profile(self, raw: dict) -> dict[str, Any]:
        """Extract key profile fields into a flat summary dict."""
        personal = raw.get("personal_info", {})
        livelihood = raw.get("livelihood_info", {})
        land = livelihood.get("land_details", livelihood.get("land_holding", {}))
        crops = livelihood.get("crops", livelihood.get("crop_patterns", []))

        income_records = raw.get("income_records", [])
        expense_records = raw.get("expense_records", [])

        avg_income = 0.0
        if income_records:
            avg_income = sum(r.get("amount", 0) for r in income_records) / len(income_records)

        avg_expense = 0.0
        if expense_records:
            avg_expense = sum(r.get("amount", 0) for r in expense_records) / len(expense_records)

        # Name can be under 'name' or 'full_name'
        name = personal.get("name", personal.get("full_name", ""))

        return {
            "name": name,
            "occupation": livelihood.get("primary_occupation", ""),
            "region": personal.get("state", personal.get("district", "")),
            "land_holding_acres": land.get("owned_acres", land.get("total_acres", 0)),
            "land_type": land.get("ownership_type", ""),
            "household_size": personal.get("dependents", personal.get("household_size", 0)),
            "avg_monthly_income": avg_income,
            "avg_monthly_expense": avg_expense,
            "crops": [c.get("crop_name", c.get("name", "")) for c in crops if (c.get("crop_name") or c.get("name"))],
            "livestock_summary": livelihood.get("livestock_summary", "None"),
            "livestock": livelihood.get("livestock", []),
            "dependents": personal.get("dependents", 0),
            "age": personal.get("age", 0),
            "location": personal.get("location", personal.get("district", "")),
        }

    def _normalize_forecast(self, raw: dict) -> dict[str, Any]:
        """Extract key forecast fields."""
        projections = raw.get("monthly_projections", [])
        if not projections:
            return raw

        inflows = [p.get("projected_inflow", 0) for p in projections]
        outflows = [p.get("projected_outflow", 0) for p in projections]

        avg_in = sum(inflows) / len(inflows) if inflows else 0
        avg_out = sum(outflows) / len(outflows) if outflows else 0

        # Find peak and lean months
        surpluses = [(p.get("month", 0), p.get("projected_inflow", 0) - p.get("projected_outflow", 0))
                     for p in projections]
        surpluses.sort(key=lambda x: x[1], reverse=True)
        peak_months = [s[0] for s in surpluses[:3]]
        lean_months = [s[0] for s in surpluses[-3:]]

        month_names = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

        return {
            "period": raw.get("forecast_period", ""),
            "avg_inflow": avg_in,
            "avg_outflow": avg_out,
            "peak_months": ", ".join(month_names[m] for m in peak_months if 1 <= m <= 12),
            "lean_months": ", ".join(month_names[m] for m in lean_months if 1 <= m <= 12),
            "projection_count": len(projections),
        }


# ---------------------------------------------------------------------------
# Stub aggregator for local development
# ---------------------------------------------------------------------------

class StubDataAggregator:
    """Returns reasonable mock data for development without running services."""

    async def fetch_profile(self, profile_id: ProfileId) -> dict[str, Any]:
        return {
            "name": "Ram Kumar",
            "occupation": "SMALL_FARMER",
            "region": "Madhya Pradesh",
            "land_holding_acres": 3.5,
            "household_size": 5,
            "avg_monthly_income": 15000,
            "avg_monthly_expense": 11000,
            "crops": ["Wheat", "Soybean", "Chana"],
            "livestock_summary": "2 cows, 4 goats",
        }

    async def fetch_risk(self, profile_id: ProfileId) -> dict[str, Any]:
        return {
            "risk_score": 420,
            "risk_category": "MEDIUM",
            "risk_factors": [
                {"name": "Income Volatility", "score": 0.35},
                {"name": "Debt Exposure", "score": 0.25},
                {"name": "Repayment History", "score": 0.15},
            ],
            "confidence_level": 0.78,
        }

    async def fetch_cashflow(self, profile_id: ProfileId) -> dict[str, Any]:
        return {
            "forecast": {
                "period": "Apr 2026 – Mar 2027",
                "avg_inflow": 14500,
                "avg_outflow": 10200,
                "peak_months": "Oct, Nov, Mar",
                "lean_months": "May, Jun, Jul",
            },
            "capacity": {
                "recommended_emi": 3500,
                "max_emi": 5000,
                "dscr": 1.4,
                "emergency_reserve": 33000,
            },
        }

    async def fetch_loans(self, profile_id: ProfileId) -> dict[str, Any]:
        return {
            "exposure": {
                "total_outstanding": 85000,
                "monthly_obligations": 4500,
                "dti_ratio": 0.30,
                "active_loan_count": 2,
                "sources": [
                    {"source_type": "FORMAL"},
                    {"source_type": "SEMI_FORMAL"},
                ],
            },
        }

    async def fetch_alerts(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        return []

    async def fetch_guidance(self, profile_id: ProfileId) -> list[dict[str, Any]]:
        return []

    async def build_full_context(self, profile_id: ProfileId) -> BorrowerContext:
        profile = await self.fetch_profile(profile_id)
        risk = await self.fetch_risk(profile_id)
        cashflow = await self.fetch_cashflow(profile_id)
        loans = await self.fetch_loans(profile_id)
        alerts = await self.fetch_alerts(profile_id)
        guidance = await self.fetch_guidance(profile_id)

        return BorrowerContext(
            profile_id=profile_id,
            profile_summary=profile,
            risk_assessment=risk,
            cashflow_forecast=cashflow.get("forecast"),
            repayment_capacity=cashflow.get("capacity"),
            loan_exposure=loans.get("exposure"),
            active_alerts=alerts,
            active_guidance=guidance,
        )
