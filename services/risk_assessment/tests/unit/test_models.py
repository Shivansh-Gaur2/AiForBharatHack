"""Unit tests for risk scoring engine (domain models)."""

import pytest

from services.risk_assessment.app.domain.models import (
    _FACTOR_WEIGHTS,
    RiskInput,
    compute_risk_score,
)
from services.shared.models import RiskCategory


def _base_input(**overrides) -> RiskInput:
    """Create a RiskInput with sensible defaults, overridable."""
    defaults = dict(
        profile_id="p1",
        income_volatility_cv=0.15,
        annual_income=120000,
        months_below_average=2,
        debt_to_income_ratio=0.2,
        total_outstanding=20000,
        active_loan_count=1,
        credit_utilisation=0.3,
        on_time_repayment_ratio=0.95,
        has_defaults=False,
        seasonal_variance=50,
        crop_diversification_index=0.6,
        weather_risk_score=10,
        market_risk_score=10,
        dependents=2,
        age=35,
        has_irrigation=True,
    )
    defaults.update(overrides)
    return RiskInput(**defaults)


class TestRiskScoreCategories:
    def test_low_risk_profile(self):
        inp = _base_input(
            income_volatility_cv=0.1,
            debt_to_income_ratio=0.1,
            on_time_repayment_ratio=1.0,
            weather_risk_score=0,
            market_risk_score=0,
        )
        result = compute_risk_score(inp)
        assert result.risk_category == RiskCategory.LOW
        assert result.risk_score < 250

    def test_high_risk_profile(self):
        inp = _base_input(
            income_volatility_cv=0.8,
            debt_to_income_ratio=0.9,
            on_time_repayment_ratio=0.3,
            has_defaults=True,
            active_loan_count=5,
            credit_utilisation=0.9,
            crop_diversification_index=0.1,
            has_irrigation=False,
            weather_risk_score=80,
            market_risk_score=70,
            dependents=8,
        )
        result = compute_risk_score(inp)
        assert result.risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH)
        assert result.risk_score >= 500

    def test_medium_risk_moderate_inputs(self):
        inp = _base_input(
            income_volatility_cv=0.4,
            debt_to_income_ratio=0.45,
            on_time_repayment_ratio=0.7,
            crop_diversification_index=0.3,
            has_irrigation=False,
        )
        result = compute_risk_score(inp)
        assert result.risk_category in (RiskCategory.MEDIUM, RiskCategory.HIGH)


class TestRiskFactors:
    """Property 8: Comprehensive Risk Scoring — all factors included."""

    def test_all_factor_types_present(self):
        inp = _base_input()
        result = compute_risk_score(inp)
        factor_types = {f.factor_type for f in result.factors}
        assert len(factor_types) == 8  # all 8 factor types

    def test_factor_weights_sum_to_one(self):
        total = sum(_FACTOR_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_score_is_bounded_0_to_1000(self):
        # Minimum risk
        low = compute_risk_score(_base_input(
            income_volatility_cv=0, debt_to_income_ratio=0,
            on_time_repayment_ratio=1.0, has_defaults=False,
            seasonal_variance=0, weather_risk_score=0, market_risk_score=0,
            crop_diversification_index=1.0, has_irrigation=True,
            dependents=1, age=35,
        ))
        assert 0 <= low.risk_score <= 1000

        # Maximum risk
        high = compute_risk_score(_base_input(
            income_volatility_cv=2.0, debt_to_income_ratio=2.0,
            on_time_repayment_ratio=0.0, has_defaults=True,
            active_loan_count=10, credit_utilisation=2.0,
            seasonal_variance=50000, weather_risk_score=100, market_risk_score=100,
            crop_diversification_index=0.0, has_irrigation=False,
            dependents=10, age=70,
        ))
        assert 0 <= high.risk_score <= 1000


class TestIncomeVolatilityFactor:
    def test_zero_cv_low_score(self):
        result = compute_risk_score(_base_input(income_volatility_cv=0.0))
        vol_factor = next(f for f in result.factors if f.factor_type.value == "INCOME_VOLATILITY")
        assert vol_factor.score == 0.0

    def test_high_cv_high_score(self):
        result = compute_risk_score(_base_input(income_volatility_cv=1.0))
        vol_factor = next(f for f in result.factors if f.factor_type.value == "INCOME_VOLATILITY")
        assert vol_factor.score == 100.0


class TestDebtExposureFactor:
    def test_zero_dti_low_score(self):
        result = compute_risk_score(_base_input(
            debt_to_income_ratio=0.0, credit_utilisation=0.0, active_loan_count=0,
        ))
        debt_factor = next(f for f in result.factors if f.factor_type.value == "DEBT_EXPOSURE")
        assert debt_factor.score == 0.0

    def test_high_dti_high_score(self):
        result = compute_risk_score(_base_input(
            debt_to_income_ratio=0.9, active_loan_count=5, credit_utilisation=0.9,
        ))
        debt_factor = next(f for f in result.factors if f.factor_type.value == "DEBT_EXPOSURE")
        assert debt_factor.score > 60


class TestRepaymentHistoryFactor:
    def test_perfect_history_zero_score(self):
        result = compute_risk_score(_base_input(
            on_time_repayment_ratio=1.0, has_defaults=False,
        ))
        repay_factor = next(f for f in result.factors if f.factor_type.value == "REPAYMENT_HISTORY")
        assert repay_factor.score == 0.0

    def test_defaults_push_score_high(self):
        result = compute_risk_score(_base_input(
            on_time_repayment_ratio=0.5, has_defaults=True,
        ))
        repay_factor = next(f for f in result.factors if f.factor_type.value == "REPAYMENT_HISTORY")
        assert repay_factor.score >= 70


class TestExplanation:
    def test_explanation_has_recommendations(self):
        result = compute_risk_score(_base_input(
            debt_to_income_ratio=0.9, income_volatility_cv=0.8,
        ))
        assert len(result.explanation.recommendations) > 0

    def test_low_risk_gets_healthy_message(self):
        result = compute_risk_score(_base_input(
            income_volatility_cv=0, debt_to_income_ratio=0,
            on_time_repayment_ratio=1.0, crop_diversification_index=1.0,
            has_irrigation=True, seasonal_variance=0,
            weather_risk_score=0, market_risk_score=0,
        ))
        assert any("healthy" in r.lower() for r in result.explanation.recommendations)

    def test_top_risk_factors_returns_correct_count(self):
        result = compute_risk_score(_base_input())
        top = result.get_top_risk_factors(3)
        assert len(top) == 3


class TestConfidence:
    def test_confidence_bounded(self):
        result = compute_risk_score(_base_input())
        assert 0.0 <= result.confidence_level <= 1.0

    def test_validity_period(self):
        low_risk = compute_risk_score(_base_input(
            income_volatility_cv=0, debt_to_income_ratio=0,
            on_time_repayment_ratio=1.0,
        ))
        # LOW risk → valid for 30 days
        delta = (low_risk.valid_until - low_risk.created_at).days
        assert delta == 30

    def test_high_risk_shorter_validity(self):
        high_risk = compute_risk_score(_base_input(
            income_volatility_cv=1.0, debt_to_income_ratio=1.0,
            on_time_repayment_ratio=0.0, has_defaults=True,
            active_loan_count=10, crop_diversification_index=0.0,
            has_irrigation=False,
        ))
        delta = (high_risk.valid_until - high_risk.created_at).days
        assert delta == 7
