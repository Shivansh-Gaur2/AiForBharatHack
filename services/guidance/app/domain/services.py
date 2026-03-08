"""Application service for the Guidance Service.

Orchestrates cross-service data retrieval and delegates to pure
domain functions for guidance generation.
"""

from __future__ import annotations

import dataclasses
import logging

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import GuidanceId, ProfileId

from .interfaces import (
    AIExplanationProvider,
    AlertDataProvider,
    CashFlowDataProvider,
    GuidanceRepository,
    LoanDataProvider,
    ProfileDataProvider,
    RiskDataProvider,
)
from .models import (
    AmountRange,
    CreditGuidance,
    LoanPurpose,
    TimingWindow,
    build_credit_guidance,
    optimize_timing_only,
    recommend_amount_only,
)
from .validators import (
    validate_amount_request,
    validate_direct_guidance_request,
    validate_guidance_request,
    validate_timing_request,
)

logger = logging.getLogger(__name__)


class GuidanceService:
    """Application service — orchestrates guidance generation workflows.

    Handles two modes:
    1. Cross-service: fetches data from Profile, Risk, CashFlow, Loan services
    2. Direct: caller provides all data (for testing or standalone use)
    """

    def __init__(
        self,
        repo: GuidanceRepository,
        risk_provider: RiskDataProvider,
        cashflow_provider: CashFlowDataProvider,
        loan_provider: LoanDataProvider,
        profile_provider: ProfileDataProvider,
        alert_provider: AlertDataProvider,
        events: AsyncEventPublisher,
        ai_provider: AIExplanationProvider | None = None,
    ) -> None:
        self._repo = repo
        self._risk = risk_provider
        self._cashflow = cashflow_provider
        self._loan = loan_provider
        self._profile = profile_provider
        self._alert = alert_provider
        self._events = events
        self._ai = ai_provider

    # ------------------------------------------------------------------
    # Command: Generate Full Credit Guidance (cross-service)
    # ------------------------------------------------------------------

    async def generate_guidance(
        self,
        profile_id: ProfileId,
        loan_purpose: str,
        requested_amount: float | None = None,
        tenure_months: int = 12,
        interest_rate_annual: float = 9.0,
    ) -> CreditGuidance:
        """Generate personalized credit guidance by aggregating all services (Req 7.1)."""
        validate_guidance_request(
            profile_id, loan_purpose, requested_amount,
            tenure_months, interest_rate_annual,
        )

        # Fetch data from all services in parallel-ish fashion
        risk_category = await self._risk.get_risk_category(profile_id)
        risk_score = await self._risk.get_risk_score(profile_id)
        projections = await self._cashflow.get_forecast_projections(profile_id)
        exposure = await self._loan.get_debt_exposure(profile_id)
        household_expense = await self._profile.get_household_expense(profile_id)  # noqa: F841

        # Fallback: if cashflow service returned no projections, we cannot
        # generate meaningful guidance.  Log a warning and flag it.
        if not projections:
            logger.warning(
                "No cashflow projections for %s — guidance will reflect zero data; "
                "ensure the cashflow service has actual forecast data for this profile.",
                profile_id,
            )

        # Record data lineage (fire-and-forget)
        try:
            from services.shared.lineage import record_data_access
            await record_data_access(
                profile_id=profile_id,
                accessed_by="guidance",
                access_type="READ",
                fields_accessed=["risk_category", "risk_score", "forecast_projections", "debt_exposure", "household_expense"],
                purpose="credit guidance generation",
            )
        except Exception:
            pass

        dti_ratio = exposure.get("dti_ratio", 0.0) if exposure else 0.0
        monthly_obligations = exposure.get("monthly_obligations", 0.0) if exposure else 0.0

        guidance = build_credit_guidance(
            profile_id=profile_id,
            loan_purpose=LoanPurpose(loan_purpose),
            requested_amount=requested_amount,
            projections=projections,
            existing_obligations=monthly_obligations,
            risk_category=risk_category,
            risk_score=risk_score,
            dti_ratio=dti_ratio,
            tenure_months=tenure_months,
            interest_rate_annual=interest_rate_annual,
        )

        guidance = await self._enrich_with_ai(guidance)

        await self._repo.save_guidance(guidance)
        await self._events.publish(DomainEvent(
            event_type="guidance.generated",
            aggregate_id=guidance.guidance_id,
            payload={
                "profile_id": profile_id,
                "loan_purpose": loan_purpose,
                "recommended_min": guidance.recommended_amount.min_amount,
                "recommended_max": guidance.recommended_amount.max_amount,
                "risk_category": risk_category,
            },
        ))
        logger.info("Generated guidance %s for profile %s", guidance.guidance_id, profile_id)
        return guidance

    # ------------------------------------------------------------------
    # Command: Generate Guidance from Direct Data
    # ------------------------------------------------------------------

    async def generate_guidance_direct(
        self,
        profile_id: ProfileId,
        loan_purpose: str,
        projections: list[tuple[int, int, float, float]],
        risk_category: str,
        risk_score: float,
        dti_ratio: float,
        existing_obligations: float,
        requested_amount: float | None = None,
        tenure_months: int = 12,
        interest_rate_annual: float = 9.0,
    ) -> CreditGuidance:
        """Generate guidance from directly-provided data (no cross-service calls)."""
        validate_direct_guidance_request(
            profile_id, loan_purpose, projections,
            risk_category, risk_score, dti_ratio, existing_obligations,
        )

        guidance = build_credit_guidance(
            profile_id=profile_id,
            loan_purpose=LoanPurpose(loan_purpose),
            requested_amount=requested_amount,
            projections=projections,
            existing_obligations=existing_obligations,
            risk_category=risk_category,
            risk_score=risk_score,
            dti_ratio=dti_ratio,
            tenure_months=tenure_months,
            interest_rate_annual=interest_rate_annual,
        )

        guidance = await self._enrich_with_ai(guidance)

        await self._repo.save_guidance(guidance)
        await self._events.publish(DomainEvent(
            event_type="guidance.generated",
            aggregate_id=guidance.guidance_id,
            payload={
                "profile_id": profile_id,
                "loan_purpose": loan_purpose,
                "mode": "direct",
            },
        ))
        logger.info("Generated guidance (direct) %s for %s", guidance.guidance_id, profile_id)
        return guidance

    # ------------------------------------------------------------------
    # Command: Optimize Timing Only (cross-service)
    # ------------------------------------------------------------------

    async def get_optimal_timing(
        self,
        profile_id: ProfileId,
        loan_amount: float,
        tenure_months: int = 12,
    ) -> TimingWindow:
        """Get optimal loan timing recommendation (Req 7.2)."""
        validate_timing_request(profile_id, loan_amount, tenure_months)

        projections = await self._cashflow.get_forecast_projections(profile_id)
        exposure = await self._loan.get_debt_exposure(profile_id)
        monthly_obligations = exposure.get("monthly_obligations", 0.0) if exposure else 0.0

        return optimize_timing_only(
            profile_id, projections, monthly_obligations, loan_amount, tenure_months,
        )

    # ------------------------------------------------------------------
    # Command: Recommend Amount Only (cross-service)
    # ------------------------------------------------------------------

    async def get_recommended_amount(
        self,
        profile_id: ProfileId,
        tenure_months: int = 12,
        interest_rate_annual: float = 9.0,
    ) -> AmountRange:
        """Get recommended loan amount range (Req 7.3)."""
        validate_amount_request(profile_id, tenure_months, interest_rate_annual)

        risk_category = await self._risk.get_risk_category(profile_id)
        projections = await self._cashflow.get_forecast_projections(profile_id)
        exposure = await self._loan.get_debt_exposure(profile_id)
        monthly_obligations = exposure.get("monthly_obligations", 0.0) if exposure else 0.0

        return recommend_amount_only(
            profile_id, projections, monthly_obligations,
            risk_category, tenure_months, interest_rate_annual,
        )

    # ------------------------------------------------------------------
    # Command: Supersede Guidance
    # ------------------------------------------------------------------

    async def supersede_guidance(self, guidance_id: GuidanceId) -> CreditGuidance:
        """Mark existing guidance as superseded (replaced by newer guidance)."""
        guidance = await self._repo.find_guidance_by_id(guidance_id)
        if guidance is None:
            raise ValueError(f"Guidance {guidance_id} not found")
        guidance.supersede()
        await self._repo.save_guidance(guidance)
        return guidance

    # ------------------------------------------------------------------
    # Command: Expire Guidance
    # ------------------------------------------------------------------

    async def expire_guidance(self, guidance_id: GuidanceId) -> CreditGuidance:
        """Mark guidance as expired."""
        guidance = await self._repo.find_guidance_by_id(guidance_id)
        if guidance is None:
            raise ValueError(f"Guidance {guidance_id} not found")
        guidance.expire()
        await self._repo.save_guidance(guidance)
        return guidance

    # ------------------------------------------------------------------
    # Internal: AI enhancement
    # ------------------------------------------------------------------

    async def _enrich_with_ai(self, guidance: CreditGuidance) -> CreditGuidance:
        """Optionally replace the guidance summary with an AI-generated one."""
        if self._ai is None:
            return guidance
        try:
            weather_market = await self._cashflow.get_weather_market_context(guidance.profile_id)
            context = {
                "purpose": guidance.loan_purpose.value.replace("_", " ").lower(),
                "min_amount": guidance.recommended_amount.min_amount,
                "max_amount": guidance.recommended_amount.max_amount,
                "timing": f"{guidance.optimal_timing.start_month}/{guidance.optimal_timing.start_year}",
                "risk": guidance.risk_summary.risk_category,
                "score": guidance.risk_summary.risk_score,
                "dti": guidance.risk_summary.dti_ratio,
                "capacity": guidance.risk_summary.repayment_capacity_pct,
                "confidence": guidance.explanation.confidence,
                "weather_condition": weather_market.get("weather_condition", "normal"),
                "market_condition": weather_market.get("market_condition", "normal"),
            }
            ai_summary = await self._ai.generate_summary(context)
            if ai_summary:
                new_explanation = dataclasses.replace(
                    guidance.explanation, summary=ai_summary
                )
                guidance.explanation = new_explanation  # type: ignore[misc]
                logger.debug("AI summary applied to guidance %s", guidance.guidance_id)
        except Exception as exc:
            logger.warning("AI enrichment failed, using template summary: %s", exc)
        return guidance

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_guidance(self, guidance_id: GuidanceId) -> CreditGuidance | None:
        """Get a specific guidance record."""
        return await self._repo.find_guidance_by_id(guidance_id)

    async def get_guidance_history(
        self,
        profile_id: ProfileId,
        limit: int = 20,
    ) -> list[CreditGuidance]:
        """Get guidance history for a profile."""
        return await self._repo.find_guidance_by_profile(profile_id, limit)

    async def get_active_guidance(
        self,
        profile_id: ProfileId,
    ) -> list[CreditGuidance]:
        """Get currently active guidance for a profile."""
        return await self._repo.find_active_guidance(profile_id)

    async def delete_profile_data(self, profile_id: ProfileId) -> int:
        """Delete all guidance records for a profile (cascade on profile deletion).

        Returns the number of guidance records deleted.
        """
        return await self._repo.delete_by_profile(profile_id)
