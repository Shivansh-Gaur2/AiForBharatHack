"""Cross-service data aggregator.

Fetches borrower data from all micro-services (Profile, Risk, CashFlow,
Loan Tracker, Early Warning, Guidance) and assembles it into a unified
``BorrowerContext`` for the AI advisor's prompts.

Uses httpx with circuit-breaker pattern for resilience.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    Uses a persistent AsyncClient for connection pooling.
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

        # Persistent client — reuses TCP connections across calls
        self._client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

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

        # Fetch both loan list and exposure
        loans, exposure = await asyncio.gather(
            self._safe_get(
                "loan",
                f"{self._loan_url}/api/v1/loans/borrower/{profile_id}",
            ),
            self._safe_get(
                "loan",
                f"{self._loan_url}/api/v1/loans/borrower/{profile_id}/exposure",
            ),
            return_exceptions=True,
        )
        result: dict[str, Any] = {}
        if isinstance(loans, dict):
            result["loans"] = loans
        if isinstance(exposure, dict):
            result["exposure"] = exposure
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
        return await self.build_partial_context(profile_id, services=None)

    async def build_partial_context(
        self,
        profile_id: ProfileId,
        services: set[str] | None = None,
    ) -> BorrowerContext:
        """Fetch only the requested services and assemble a BorrowerContext.

        Args:
            profile_id: The borrower's profile ID.
            services: Set of service names to fetch. ``None`` means all services.
                      Valid keys: 'profile', 'risk', 'cashflow', 'loan', 'alert', 'guidance'.
        """
        fetch_all = services is None
        context = BorrowerContext(profile_id=profile_id)
        unavailable: list[str] = []

        # Build coroutine list in a fixed order so we can unpack results
        _ALL = ["profile", "risk", "cashflow", "loan", "alert", "guidance"]
        fetch_map = {
            "profile":  lambda: self.fetch_profile(profile_id),
            "risk":     lambda: self.fetch_risk(profile_id),
            "cashflow": lambda: self.fetch_cashflow(profile_id),
            "loan":     lambda: self.fetch_loans(profile_id),
            "alert":    lambda: self.fetch_alerts(profile_id),
            "guidance": lambda: self.fetch_guidance(profile_id),
        }
        active = [k for k in _ALL if fetch_all or k in (services or set())]
        coros = [fetch_map[k]() for k in active]

        results = await asyncio.gather(*coros, return_exceptions=True)
        result_map = dict(zip(active, results))

        # --- Profile ---
        profile_data = result_map.get("profile")
        if isinstance(profile_data, dict) and profile_data:
            context.profile_summary = self._normalize_profile(profile_data)
        elif "profile" in active:
            unavailable.append("profile")

        # --- Risk ---
        risk_data = result_map.get("risk")
        if isinstance(risk_data, dict) and risk_data:
            context.risk_assessment = risk_data
        elif "risk" in active:
            unavailable.append("risk")

        # --- Cashflow ---
        cashflow_data = result_map.get("cashflow")
        if isinstance(cashflow_data, dict):
            forecast = cashflow_data.get("forecast", {})
            capacity = cashflow_data.get("capacity", {})
            if forecast:
                context.cashflow_forecast = self._normalize_forecast(forecast)
            if capacity:
                context.repayment_capacity = capacity
            if not forecast and not capacity and "cashflow" in active:
                unavailable.append("cashflow")
        elif "cashflow" in active:
            unavailable.append("cashflow")

        # --- Loans ---
        loan_data = result_map.get("loan")
        if isinstance(loan_data, dict):
            exposure = loan_data.get("exposure", {})
            loans = loan_data.get("loans", {})
            if exposure:
                context.loan_exposure = exposure
            if isinstance(loans, dict) and loans.get("loans"):
                context.active_loans = loans["loans"][:10]
            if not exposure and not (isinstance(loans, dict) and loans.get("loans")) and "loan" in active:
                unavailable.append("loan")
        elif "loan" in active:
            unavailable.append("loan")

        # --- Alerts ---
        alert_data = result_map.get("alert")
        if isinstance(alert_data, list):
            context.active_alerts = alert_data[:5]
        elif "alert" in active:
            unavailable.append("alert")

        # --- Guidance ---
        guidance_data = result_map.get("guidance")
        if isinstance(guidance_data, list):
            context.active_guidance = guidance_data[:3]
        elif "guidance" in active:
            unavailable.append("guidance")

        context.unavailable_services = unavailable
        context.context_fetched_at = time.time()

        logger.info(
            "Built context for %s: has_data=%s, fetched=%s, unavailable=%s",
            profile_id, context.has_data(), active, unavailable,
        )
        return context

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _safe_get(self, service: str, url: str) -> dict[str, Any]:
        """HTTP GET with circuit breaker and error handling. Reuses persistent client."""
        breaker = self._breakers.get(service)
        if breaker and not breaker.is_call_permitted():
            logger.debug("Circuit open for %s — skipping %s", service, url)
            return {}

        try:
            resp = await self._client.get(url)
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
        """Extract key profile fields into a flat summary dict.

        Maps the Profile API's nested structure to a flat context dict.
        Field names here match what the Profile Service actually returns.
        """
        personal = raw.get("personal_info", {}) or {}
        livelihood = raw.get("livelihood_info", {}) or {}
        # Profile API returns "land_details" (request-schema key); domain may return "land_holding"
        land = livelihood.get("land_details", livelihood.get("land_holding", {})) or {}
        # Profile API returns "crops"; domain may return "crop_patterns"
        crops = livelihood.get("crops", livelihood.get("crop_patterns", [])) or []
        livestock_list = livelihood.get("livestock", []) or []

        # Build a human-readable livestock summary from the list
        livestock_parts = [
            f"{l.get('count', 0)} {l.get('animal_type', '')}"
            for l in livestock_list
            if l.get("count") and l.get("animal_type")
        ]
        livestock_summary = ", ".join(livestock_parts) if livestock_parts else "None"

        income_records = raw.get("income_records", []) or []
        expense_records = raw.get("expense_records", []) or []

        # Average over the most recent 12 months to avoid stale data skewing figures
        def _avg_last_12(records: list) -> float:
            if not records:
                return 0.0
            sorted_recs = sorted(
                records,
                key=lambda r: (r.get("year", 0), r.get("month", 0)),
                reverse=True,
            )
            recent = sorted_recs[:12]
            return sum(r.get("amount", 0) for r in recent) / len(recent)

        dependents = personal.get("dependents", 0)
        return {
            "name": personal.get("name", ""),           # correct key (not full_name)
            "age": personal.get("age", "N/A"),
            "occupation": livelihood.get("primary_occupation", ""),
            "secondary_occupations": livelihood.get("secondary_occupations", []),
            "region": (
                personal.get("location")
                or personal.get("state")
                or personal.get("district", "")
            ),
            "state": personal.get("state", ""),
            "district": personal.get("district", ""),
            "land_holding_acres": (
                land.get("total_acres")
                or land.get("owned_acres", 0) + land.get("leased_acres", 0)
            ),
            "land_type": land.get("ownership_type", "leased" if land.get("leased_acres", 0) > 0 else "owned"),
            "household_size": dependents + 1,           # dependents + the borrower themselves
            "dependents": dependents,
            "avg_monthly_income": _avg_last_12(income_records),
            "avg_monthly_expense": _avg_last_12(expense_records),
            "crops": [c.get("crop_name", "") for c in crops if c.get("crop_name")],
            "livestock_summary": livestock_summary,     # built from list, not missing field
        }

    def _normalize_forecast(self, raw: dict) -> dict[str, Any]:
        """Extract key forecast fields into a standard shape.

        Always returns keys that to_prompt_context() expects:
        period, avg_inflow, avg_outflow, peak_months, lean_months.
        Falls back to top-level keys when monthly_projections is absent
        rather than returning the raw dict with mismatched keys.
        """
        projections = raw.get("monthly_projections", []) or []

        month_names = [
            "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

        if projections:
            inflows = [p.get("projected_inflow", 0) for p in projections]
            outflows = [p.get("projected_outflow", 0) for p in projections]
            avg_in = sum(inflows) / len(inflows)
            avg_out = sum(outflows) / len(outflows)

            surpluses = [
                (p.get("month", 0), p.get("projected_inflow", 0) - p.get("projected_outflow", 0))
                for p in projections
            ]
            surpluses.sort(key=lambda x: x[1], reverse=True)
            peak = [s[0] for s in surpluses[:3]]
            lean = [s[0] for s in surpluses[-3:]]

            return {
                "period": raw.get("forecast_period", raw.get("period", "")),
                "avg_inflow": avg_in,
                "avg_outflow": avg_out,
                "peak_months": ", ".join(month_names[m] for m in peak if 1 <= m <= 12),
                "lean_months": ", ".join(month_names[m] for m in lean if 1 <= m <= 12),
                "projection_count": len(projections),
            }

        # No projections — map whatever top-level aggregate keys exist
        # so the prompt context still gets real values instead of 'N/A'
        return {
            "period": raw.get("forecast_period", raw.get("period", "N/A")),
            "avg_inflow": raw.get("avg_inflow", raw.get("total_inflow", 0)),
            "avg_outflow": raw.get("avg_outflow", raw.get("total_outflow", 0)),
            "peak_months": raw.get("peak_months", "N/A"),
            "lean_months": raw.get("lean_months", "N/A"),
            "projection_count": 0,
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

        context = BorrowerContext(
            profile_id=profile_id,
            profile_summary=profile or None,
            risk_assessment=risk or None,
            cashflow_forecast=cashflow.get("forecast") if cashflow else None,
            repayment_capacity=cashflow.get("capacity") if cashflow else None,
            loan_exposure=loans.get("exposure") if loans else None,
            active_alerts=alerts,
            active_guidance=guidance,
            context_fetched_at=time.time(),
        )
        return context

    async def build_partial_context(
        self,
        profile_id: ProfileId,
        services: set[str] | None = None,
    ) -> BorrowerContext:
        """Stub ignores the services filter and always returns full mock data."""
        return await self.build_full_context(profile_id)
