"""Risk Assessment domain service — orchestrates risk scoring use cases.

Consumes data from Profile and Loan Tracker services (via ports),
computes risk scores using the AI/ML decision engine (gb-risk-v2),
stores assessments, and publishes events.

Falls back to rules-v1 when the AI model is unavailable.
"""

from __future__ import annotations

import logging

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import ProfileId

from .interfaces import (
    LoanDataProvider,
    ProfileDataProvider,
    RiskAssessmentRepository,
)
from .models import RiskAssessment, RiskInput, compute_risk_score

logger = logging.getLogger(__name__)


def _ai_assess(risk_input: RiskInput) -> RiskAssessment | None:
    """Attempt AI-based risk scoring; return None on failure."""
    try:
        from services.shared.ai import get_risk_model, engineer_risk_features

        model = get_risk_model()
        raw_features = {
            "income_volatility_cv": risk_input.income_volatility_cv,
            "annual_income": risk_input.annual_income,
            "months_below_average": risk_input.months_below_average,
            "debt_to_income_ratio": risk_input.debt_to_income_ratio,
            "total_outstanding": risk_input.total_outstanding,
            "active_loan_count": risk_input.active_loan_count,
            "credit_utilisation": risk_input.credit_utilisation,
            "on_time_repayment_ratio": risk_input.on_time_repayment_ratio,
            "has_defaults": risk_input.has_defaults,
            "seasonal_variance": risk_input.seasonal_variance,
            "crop_diversification_index": risk_input.crop_diversification_index,
            "weather_risk_score": risk_input.weather_risk_score,
            "market_risk_score": risk_input.market_risk_score,
            "dependents": risk_input.dependents,
            "age": risk_input.age,
            "has_irrigation": risk_input.has_irrigation,
        }

        prediction = model.predict_risk_score(raw_features)

        # Convert AI prediction into a domain RiskAssessment
        from datetime import UTC, datetime, timedelta
        from services.shared.models import RiskCategory, generate_id
        from .models import RiskExplanation, RiskFactor, RiskFactorType

        cat_map = {
            "LOW": RiskCategory.LOW,
            "MEDIUM": RiskCategory.MEDIUM,
            "HIGH": RiskCategory.HIGH,
            "VERY_HIGH": RiskCategory.VERY_HIGH,
        }
        risk_category = cat_map.get(prediction.category, RiskCategory.MEDIUM)

        # Build factors from feature importances
        factor_type_map = {
            "income_cv": RiskFactorType.INCOME_VOLATILITY,
            "dti_ratio": RiskFactorType.DEBT_EXPOSURE,
            "on_time_ratio": RiskFactorType.REPAYMENT_HISTORY,
            "seasonal_var_norm": RiskFactorType.SEASONAL_RISK,
            "weather_risk_norm": RiskFactorType.WEATHER_RISK,
            "market_risk_norm": RiskFactorType.MARKET_RISK,
            "dependency_ratio": RiskFactorType.DEMOGRAPHIC,
            "crop_diversity": RiskFactorType.CROP_DIVERSIFICATION,
        }
        ai_factors = []
        for feat, importance in prediction.feature_importances.items():
            if feat in factor_type_map:
                ai_factors.append(RiskFactor(
                    factor_type=factor_type_map[feat],
                    score=round(importance * 100, 1),
                    weight=importance,
                    description=f"AI-scored: {feat}={importance:.3f}",
                ))

        # Fill missing factor types with zero-score entries
        existing_types = {f.factor_type for f in ai_factors}
        for ft in RiskFactorType:
            if ft not in existing_types:
                ai_factors.append(RiskFactor(
                    factor_type=ft, score=0, weight=0.0,
                    description=f"No signal from AI model for {ft.value}",
                ))

        explanation = RiskExplanation(
            summary=f"AI risk score {prediction.score}/1000 ({prediction.category}). "
                    f"Model: {prediction.model_version}.",
            key_factors=[f for f in prediction.explanation_fragments[:3]],
            recommendations=prediction.explanation_fragments[3:] or [
                "Maintain current financial practices."
            ],
            confidence_note=f"AI confidence {prediction.confidence:.0%}.",
        )

        valid_days = 30 if risk_category in (RiskCategory.LOW, RiskCategory.MEDIUM) else 7
        now = datetime.now(UTC)

        return RiskAssessment(
            assessment_id=generate_id(),
            profile_id=risk_input.profile_id,
            risk_score=prediction.score,
            risk_category=risk_category,
            confidence_level=prediction.confidence,
            factors=ai_factors,
            explanation=explanation,
            valid_until=now + timedelta(days=valid_days),
            created_at=now,
            updated_at=now,
            model_version=prediction.model_version,
        )
    except Exception:
        logger.warning("AI risk model unavailable, falling back to rules-v1", exc_info=True)
        return None


class RiskAssessmentService:
    """Application service for risk assessment (Req 4.1–4.5)."""

    def __init__(
        self,
        repo: RiskAssessmentRepository,
        profile_provider: ProfileDataProvider,
        loan_provider: LoanDataProvider,
        events: AsyncEventPublisher,
        weather_market_provider=None,
    ) -> None:
        self._repo = repo
        self._profiles = profile_provider
        self._loans = loan_provider
        self._events = events
        self._weather_market = weather_market_provider

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

        # Record data lineage (fire-and-forget)
        try:
            from services.shared.lineage import record_data_access
            await record_data_access(
                profile_id=profile_id,
                accessed_by="risk-assessment",
                access_type="READ",
                fields_accessed=["income_volatility", "personal_info", "debt_exposure", "repayment_stats"],
                purpose="risk assessment scoring",
            )
        except Exception:
            pass  # lineage is best-effort

        risk_input = RiskInput(
            profile_id=profile_id,
            income_volatility_cv=volatility.get("coefficient_of_variation", 0.0),
            annual_income=volatility.get("annual_income", 0.0),
            months_below_average=volatility.get("months_below_average", 0),
            debt_to_income_ratio=exposure.get("debt_to_income_ratio", 0.0),
            total_outstanding=exposure.get("total_outstanding", 0.0),
            active_loan_count=exposure.get("active_loan_count", 0),
            credit_utilisation=exposure.get("credit_utilisation", 0.0),
            on_time_repayment_ratio=repayment.get("on_time_ratio", 0.0),
            has_defaults=repayment.get("has_defaults", False),
            seasonal_variance=volatility.get("seasonal_variance", 0.0),
            crop_diversification_index=personal.get("crop_diversification_index", 0.0),
            weather_risk_score=await self._get_weather_risk(personal),
            market_risk_score=await self._get_market_risk(personal),
            dependents=personal.get("dependents", 0),
            age=personal.get("age", 0),
            has_irrigation=personal.get("has_irrigation", False),
        )

        # Prefer AI model (gb-risk-v2); fall back to rules-v1
        assessment = _ai_assess(risk_input) or compute_risk_score(risk_input)
        await self._repo.save(assessment)

        await self._events.publish(DomainEvent(
            event_type="risk.assessed",
            aggregate_id=assessment.assessment_id,
            payload={
                "profile_id": profile_id,
                "risk_score": assessment.risk_score,
                "risk_category": assessment.risk_category.value,
                "confidence": assessment.confidence_level,
                "model_version": assessment.model_version,
            },
        ))

        return assessment

    async def assess_risk_with_input(self, risk_input: RiskInput) -> RiskAssessment:
        """Score from a pre-built RiskInput (useful for testing / direct calls)."""
        assessment = _ai_assess(risk_input) or compute_risk_score(risk_input)
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

    # ------------------------------------------------------------------
    # Internal helpers for external risk data
    # ------------------------------------------------------------------

    async def _get_weather_risk(self, personal: dict) -> float:
        """Fetch weather risk score from external API via provider."""
        if self._weather_market is None:
            return 0.0
        try:
            district = personal.get("district", "unknown")
            if district == "unknown":
                return 0.0
            return await self._weather_market.get_weather_risk(district)
        except Exception:
            logger.warning("Weather risk lookup failed", exc_info=True)
            return 0.0

    async def _get_market_risk(self, personal: dict) -> float:
        """Fetch market risk score from external API via provider."""
        if self._weather_market is None:
            return 0.0
        try:
            crop = personal.get("primary_crop", "unknown")
            state = personal.get("state", "unknown")
            if crop == "unknown":
                return 0.0
            return await self._weather_market.get_market_risk(crop, state)
        except Exception:
            logger.warning("Market risk lookup failed", exc_info=True)
            return 0.0

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
