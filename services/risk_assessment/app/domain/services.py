"""Risk Assessment domain service — orchestrates risk scoring use cases.

Consumes data from Profile and Loan Tracker services (via ports),
computes risk scores, stores assessments, and publishes events.
"""

from __future__ import annotations

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import ProfileId

from .interfaces import (
    LoanDataProvider,
    ProfileDataProvider,
    RiskAssessmentRepository,
)
from .models import RiskAssessment, RiskInput, compute_risk_score


class RiskAssessmentService:
    """Application service for risk assessment (Req 4.1–4.5)."""

    def __init__(
        self,
        repo: RiskAssessmentRepository,
        profile_provider: ProfileDataProvider,
        loan_provider: LoanDataProvider,
        events: AsyncEventPublisher,
    ) -> None:
        self._repo = repo
        self._profiles = profile_provider
        self._loans = loan_provider
        self._events = events

    async def assess_risk(self, profile_id: ProfileId) -> RiskAssessment:
        """Generate a full risk assessment (Property 8).

        Gathers data from profile + loan services, scores, persists, and
        publishes a domain event.
        """
        # Gather inputs from other services (via ports)
        volatility = await self._profiles.get_income_volatility(profile_id)
        personal = await self._profiles.get_personal_info(profile_id)
        exposure = await self._loans.get_debt_exposure(profile_id)
        repayment = await self._loans.get_repayment_stats(profile_id)

        risk_input = RiskInput(
            profile_id=profile_id,
            income_volatility_cv=volatility.get("coefficient_of_variation", 0.0),
            annual_income=volatility.get("annual_income", 0.0),
            months_below_average=volatility.get("months_below_average", 0),
            debt_to_income_ratio=exposure.get("debt_to_income_ratio", 0.0),
            total_outstanding=exposure.get("total_outstanding", 0.0),
            active_loan_count=exposure.get("active_loan_count", 0),
            credit_utilisation=exposure.get("credit_utilisation", 0.0),
            on_time_repayment_ratio=repayment.get("on_time_ratio", 1.0),
            has_defaults=repayment.get("has_defaults", False),
            seasonal_variance=volatility.get("seasonal_variance", 0.0),
            crop_diversification_index=personal.get("crop_diversification_index", 0.5),
            weather_risk_score=0.0,      # Phase 3: external data
            market_risk_score=0.0,       # Phase 3: external data
            dependents=personal.get("dependents", 0),
            age=personal.get("age", 30),
            has_irrigation=personal.get("has_irrigation", False),
        )

        assessment = compute_risk_score(risk_input)
        await self._repo.save(assessment)

        await self._events.publish(DomainEvent(
            event_type="risk.assessed",
            aggregate_id=assessment.assessment_id,
            payload={
                "profile_id": profile_id,
                "risk_score": assessment.risk_score,
                "risk_category": assessment.risk_category.value,
                "confidence": assessment.confidence_level,
            },
        ))

        return assessment

    async def assess_risk_with_input(self, risk_input: RiskInput) -> RiskAssessment:
        """Score from a pre-built RiskInput (useful for testing / direct calls)."""
        assessment = compute_risk_score(risk_input)
        await self._repo.save(assessment)

        await self._events.publish(DomainEvent(
            event_type="risk.assessed",
            aggregate_id=assessment.assessment_id,
            payload={
                "profile_id": risk_input.profile_id,
                "risk_score": assessment.risk_score,
                "risk_category": assessment.risk_category.value,
            },
        ))

        return assessment

    async def get_latest_assessment(
        self, profile_id: ProfileId,
    ) -> RiskAssessment | None:
        return await self._repo.find_latest(profile_id)

    async def get_assessment(self, assessment_id: str) -> RiskAssessment | None:
        return await self._repo.find_by_id(assessment_id)

    async def get_assessment_history(
        self, profile_id: ProfileId, limit: int = 10,
    ) -> list[RiskAssessment]:
        return await self._repo.find_history(profile_id, limit=limit)

    async def explain_risk(self, assessment_id: str) -> dict | None:
        """Return a simplified explanation of a risk assessment."""
        assessment = await self._repo.find_by_id(assessment_id)
        if assessment is None:
            return None
        return {
            "risk_score": assessment.risk_score,
            "category": assessment.risk_category.value,
            "summary": assessment.explanation.summary,
            "key_factors": assessment.explanation.key_factors,
            "recommendations": assessment.explanation.recommendations,
            "confidence": assessment.explanation.confidence_note,
            "top_factors": [
                {
                    "type": f.factor_type.value,
                    "score": f.score,
                    "weight": f.weight,
                    "description": f.description,
                }
                for f in assessment.get_top_risk_factors(3)
            ],
        }
