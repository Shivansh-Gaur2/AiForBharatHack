"""Unit tests for Guidance Service domain models.

Tests pure business logic functions — no I/O, no infrastructure.
"""

from __future__ import annotations

import pytest

from services.guidance.app.domain.models import (
    AmountRange,
    ConfidenceLevel,
    CreditGuidance,
    GuidanceStatus,
    LoanPurpose,
    MonthlyCapacity,
    TimingSuitability,
    TimingWindow,
    build_credit_guidance,
    build_explanation,
    build_risk_summary,
    compute_monthly_capacities,
    compute_seasonal_insights,
    compute_suggested_terms,
    find_optimal_timing,
    generate_alternative_options,
    optimize_timing_only,
    recommend_amount_only,
    recommend_loan_amount,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_projections() -> list[tuple[int, int, float, float]]:
    """12-month seasonal projections."""
    return [
        (1, 2026, 12000, 8000),
        (2, 2026, 14000, 7500),
        (3, 2026, 16000, 8000),
        (4, 2026, 8000, 7000),
        (5, 2026, 7000, 7500),
        (6, 2026, 9000, 8000),
        (7, 2026, 10000, 9000),
        (8, 2026, 11000, 8500),
        (9, 2026, 13000, 8000),
        (10, 2026, 15000, 8000),
        (11, 2026, 13000, 7500),
        (12, 2026, 11000, 8000),
    ]


@pytest.fixture()
def sample_capacities(sample_projections) -> list[MonthlyCapacity]:
    return compute_monthly_capacities(sample_projections, existing_obligations=3000)


# ---------------------------------------------------------------------------
# Monthly Capacity Tests
# ---------------------------------------------------------------------------
class TestMonthlyCapacities:
    def test_compute_basic(self, sample_projections):
        caps = compute_monthly_capacities(sample_projections, existing_obligations=0)
        assert len(caps) == 12
        # January: 12000 - 8000 - 0 = 4000
        assert caps[0].surplus == 4000
        assert caps[0].month == 1
        assert caps[0].year == 2026

    def test_compute_with_obligations(self, sample_projections):
        caps = compute_monthly_capacities(sample_projections, existing_obligations=3000)
        # January: 12000 - 8000 - 3000 = 1000
        assert caps[0].surplus == 1000
        # May: 7000 - 7500 - 3000 = -3500
        assert caps[4].surplus == -3500

    def test_empty_projections(self):
        caps = compute_monthly_capacities([], existing_obligations=0)
        assert caps == []

    def test_single_month(self):
        caps = compute_monthly_capacities([(6, 2026, 10000, 5000)], existing_obligations=1000)
        assert len(caps) == 1
        assert caps[0].surplus == 4000


# ---------------------------------------------------------------------------
# Seasonal Insights Tests
# ---------------------------------------------------------------------------
class TestSeasonalInsights:
    def test_compute_insights(self, sample_capacities):
        insights = compute_seasonal_insights(sample_capacities)
        assert len(insights) > 0
        seasons = {i.season for i in insights}
        # Should cover at least 2 seasons
        assert len(seasons) >= 2

    def test_insights_suitability(self, sample_capacities):
        insights = compute_seasonal_insights(sample_capacities)
        for insight in insights:
            assert insight.suitability in (
                TimingSuitability.OPTIMAL, TimingSuitability.GOOD,
                TimingSuitability.ACCEPTABLE, TimingSuitability.POOR,
            )

    def test_deficit_counted(self):
        # All deficit months
        caps = [
            MonthlyCapacity(m, 2026, 5000, 8000, 0, -3000)
            for m in range(6, 11)  # Kharif
        ]
        insights = compute_seasonal_insights(caps)
        kharif = [i for i in insights if i.season == "KHARIF"]
        assert len(kharif) == 1
        assert kharif[0].months_in_deficit == 5
        assert kharif[0].suitability == TimingSuitability.POOR


# ---------------------------------------------------------------------------
# Loan Amount Recommendation Tests
# ---------------------------------------------------------------------------
class TestRecommendAmount:
    def test_low_risk_higher_amount(self, sample_capacities):
        low = recommend_loan_amount(sample_capacities, None, "LOW", 12)
        high = recommend_loan_amount(sample_capacities, None, "HIGH", 12)
        assert low.max_amount > high.max_amount

    def test_empty_capacities(self):
        result = recommend_loan_amount([], None, "MEDIUM", 12)
        assert result.min_amount == 0.0
        assert result.max_amount == 0.0

    def test_requested_amount_within_range(self, sample_capacities):
        result = recommend_loan_amount(sample_capacities, 20000, "MEDIUM", 12)
        assert result.max_amount >= 0
        assert result.min_amount >= 0

    def test_requested_too_much(self, sample_capacities):
        # Request 10 crore — should be capped
        result = recommend_loan_amount(sample_capacities, 10_000_000, "LOW", 12)
        assert result.max_amount < 10_000_000

    def test_longer_tenure_higher_amount(self, sample_capacities):
        short = recommend_loan_amount(sample_capacities, None, "MEDIUM", 6)
        long = recommend_loan_amount(sample_capacities, None, "MEDIUM", 24)
        assert long.max_amount >= short.max_amount

    def test_zero_interest(self, sample_capacities):
        result = recommend_loan_amount(
            sample_capacities, None, "MEDIUM", 12, interest_rate_annual=0,
        )
        assert result.max_amount >= 0

    def test_all_deficit_months(self):
        caps = [MonthlyCapacity(m, 2026, 5000, 8000, 0, -3000) for m in range(1, 13)]
        result = recommend_loan_amount(caps, None, "LOW", 12)
        assert result.max_amount == 0.0


# ---------------------------------------------------------------------------
# Timing Tests
# ---------------------------------------------------------------------------
class TestFindOptimalTiming:
    def test_finds_best_window(self, sample_capacities):
        timing = find_optimal_timing(sample_capacities, tenure_months=6)
        assert timing.suitability in (
            TimingSuitability.OPTIMAL, TimingSuitability.GOOD,
            TimingSuitability.ACCEPTABLE, TimingSuitability.POOR,
        )
        assert timing.reason

    def test_empty_capacities(self):
        timing = find_optimal_timing([], tenure_months=6)
        assert timing.suitability == TimingSuitability.POOR

    def test_single_month(self):
        caps = [MonthlyCapacity(3, 2026, 20000, 5000, 0, 15000)]
        timing = find_optimal_timing(caps, tenure_months=1)
        assert timing.start_month == 3
        assert timing.end_month == 3

    def test_prefers_surplus_period(self):
        # 6 low months, then 6 high months
        caps = (
            [MonthlyCapacity(m, 2026, 5000, 8000, 0, -3000) for m in range(1, 7)]
            + [MonthlyCapacity(m, 2026, 20000, 5000, 0, 15000) for m in range(7, 13)]
        )
        timing = find_optimal_timing(caps, tenure_months=6)
        assert timing.start_month >= 7  # Should start in the high period


# ---------------------------------------------------------------------------
# Suggested Terms Tests
# ---------------------------------------------------------------------------
class TestSuggestedTerms:
    def test_compute_terms(self):
        amount = AmountRange(min_amount=40000, max_amount=60000)
        terms = compute_suggested_terms(amount, 12, 9.0, "MEDIUM")
        assert terms.tenure_months == 12
        assert terms.emi_amount > 0
        assert terms.total_repayment > 50000  # More than principal

    def test_formal_source_for_large(self):
        amount = AmountRange(min_amount=100000, max_amount=200000)
        terms = compute_suggested_terms(amount, 24, 9.0, "LOW")
        assert terms.source_recommendation == "FORMAL"

    def test_semi_formal_for_small(self):
        amount = AmountRange(min_amount=5000, max_amount=15000)
        terms = compute_suggested_terms(amount, 6, 12.0, "LOW")
        assert terms.source_recommendation == "SEMI_FORMAL"


# ---------------------------------------------------------------------------
# Risk Summary Tests
# ---------------------------------------------------------------------------
class TestRiskSummary:
    def test_build_summary(self):
        summary = build_risk_summary("MEDIUM", 450, 0.3, 5000, 15000)
        assert summary.risk_category == "MEDIUM"
        assert summary.risk_score == 450
        assert summary.repayment_capacity_pct > 0

    def test_high_dti_factor(self):
        summary = build_risk_summary("HIGH", 650, 0.6, 2000, 15000)
        assert "High debt-to-income ratio" in summary.key_risk_factors

    def test_no_factors_for_low_risk(self):
        summary = build_risk_summary("LOW", 200, 0.1, 10000, 15000)
        assert "No significant risk factors identified" in summary.key_risk_factors


# ---------------------------------------------------------------------------
# Alternative Options Tests
# ---------------------------------------------------------------------------
class TestAlternativeOptions:
    def test_crop_cultivation_has_government_scheme(self):
        options = generate_alternative_options("LOW", LoanPurpose.CROP_CULTIVATION, 100000)
        types = {o.option_type for o in options}
        assert "GOVERNMENT_SCHEME" in types
        assert "CROP_INSURANCE" in types

    def test_high_risk_has_restructuring(self):
        options = generate_alternative_options("HIGH", LoanPurpose.WORKING_CAPITAL, 50000)
        types = {o.option_type for o in options}
        assert "DEBT_RESTRUCTURING" in types

    def test_small_amount_has_shg(self):
        options = generate_alternative_options("LOW", LoanPurpose.LIVESTOCK_PURCHASE, 50000)
        types = {o.option_type for o in options}
        assert "SHG_LOAN" in types

    def test_large_amount_no_shg(self):
        options = generate_alternative_options("LOW", LoanPurpose.HOUSING, 500000)
        types = {o.option_type for o in options}
        assert "SHG_LOAN" not in types


# ---------------------------------------------------------------------------
# Explanation Tests
# ---------------------------------------------------------------------------
class TestBuildExplanation:
    def test_has_all_steps(self, sample_capacities):
        risk = build_risk_summary("MEDIUM", 450, 0.3, 3000, 12000)
        timing = find_optimal_timing(sample_capacities, 12)
        amount = AmountRange(min_amount=30000, max_amount=60000)
        explanation = build_explanation(
            LoanPurpose.CROP_CULTIVATION, risk, timing, amount, sample_capacities,
        )
        assert len(explanation.reasoning_steps) == 5
        factors = {s.factor for s in explanation.reasoning_steps}
        assert "Risk Profile" in factors
        assert "Current Debt Burden" in factors
        assert "Cash Flow Stability" in factors

    def test_confidence_high_for_low_risk(self):
        # All positive indicators
        caps = [MonthlyCapacity(m, 2026, 20000, 5000, 0, 15000) for m in range(1, 13)]
        risk = build_risk_summary("LOW", 200, 0.1, 15000, 20000)
        timing = TimingWindow(1, 2026, 12, 2026, TimingSuitability.OPTIMAL,
                              "Strong surplus")
        amount = AmountRange(min_amount=50000, max_amount=100000)
        explanation = build_explanation(LoanPurpose.WORKING_CAPITAL, risk, timing, amount, caps)
        assert explanation.confidence == ConfidenceLevel.HIGH

    def test_confidence_low_for_many_negatives(self):
        # All deficit
        caps = [MonthlyCapacity(m, 2026, 5000, 8000, 3000, -6000) for m in range(1, 13)]
        risk = build_risk_summary("VERY_HIGH", 800, 0.7, -6000, 5000)
        timing = TimingWindow(1, 2026, 12, 2026, TimingSuitability.POOR,
                              "Weak cash flow")
        amount = AmountRange(min_amount=0, max_amount=5000)
        explanation = build_explanation(LoanPurpose.MEDICAL, risk, timing, amount, caps)
        assert explanation.confidence == ConfidenceLevel.LOW
        assert len(explanation.caveats) > 0

    def test_summary_includes_amount(self, sample_capacities):
        risk = build_risk_summary("MEDIUM", 450, 0.3, 3000, 12000)
        timing = find_optimal_timing(sample_capacities, 12)
        amount = AmountRange(min_amount=30000, max_amount=60000)
        explanation = build_explanation(
            LoanPurpose.CROP_CULTIVATION, risk, timing, amount, sample_capacities,
        )
        assert "30,000" in explanation.summary
        assert "60,000" in explanation.summary


# ---------------------------------------------------------------------------
# Full Guidance Build Tests
# ---------------------------------------------------------------------------
class TestBuildCreditGuidance:
    def test_builds_complete_guidance(self, sample_projections):
        guidance = build_credit_guidance(
            profile_id="prof-1",
            loan_purpose=LoanPurpose.CROP_CULTIVATION,
            requested_amount=50000,
            projections=sample_projections,
            existing_obligations=3000,
            risk_category="MEDIUM",
            risk_score=450,
            dti_ratio=0.3,
        )
        assert guidance.guidance_id
        assert guidance.profile_id == "prof-1"
        assert guidance.loan_purpose == LoanPurpose.CROP_CULTIVATION
        assert guidance.requested_amount == 50000
        assert guidance.recommended_amount.min_amount >= 0
        assert guidance.recommended_amount.max_amount >= guidance.recommended_amount.min_amount
        assert guidance.optimal_timing.start_month >= 1
        assert guidance.suggested_terms.emi_amount >= 0
        assert guidance.risk_summary.risk_category == "MEDIUM"
        assert len(guidance.explanation.reasoning_steps) == 5
        assert guidance.status == GuidanceStatus.ACTIVE

    def test_no_requested_amount(self, sample_projections):
        guidance = build_credit_guidance(
            profile_id="prof-2",
            loan_purpose=LoanPurpose.LIVESTOCK_PURCHASE,
            requested_amount=None,
            projections=sample_projections,
            existing_obligations=0,
            risk_category="LOW",
            risk_score=200,
            dti_ratio=0.1,
        )
        assert guidance.requested_amount is None
        assert guidance.recommended_amount.max_amount > 0

    def test_high_risk_gets_alternatives(self, sample_projections):
        guidance = build_credit_guidance(
            profile_id="prof-3",
            loan_purpose=LoanPurpose.CROP_CULTIVATION,
            requested_amount=None,
            projections=sample_projections,
            existing_obligations=5000,
            risk_category="HIGH",
            risk_score=700,
            dti_ratio=0.6,
        )
        types = {o.option_type for o in guidance.alternative_options}
        assert "DEBT_RESTRUCTURING" in types


# ---------------------------------------------------------------------------
# Guidance Lifecycle Tests
# ---------------------------------------------------------------------------
class TestGuidanceLifecycle:
    def _make_guidance(self) -> CreditGuidance:
        return build_credit_guidance(
            profile_id="life-1",
            loan_purpose=LoanPurpose.WORKING_CAPITAL,
            requested_amount=None,
            projections=[(m, 2026, 15000, 8000) for m in range(1, 13)],
            existing_obligations=2000,
            risk_category="MEDIUM",
            risk_score=400,
            dti_ratio=0.25,
        )

    def test_is_active(self):
        g = self._make_guidance()
        assert g.is_active()

    def test_expire(self):
        g = self._make_guidance()
        g.expire()
        assert g.status == GuidanceStatus.EXPIRED
        assert not g.is_active()

    def test_supersede(self):
        g = self._make_guidance()
        g.supersede()
        assert g.status == GuidanceStatus.SUPERSEDED
        assert not g.is_active()


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------
class TestOptimizeTimingOnly:
    def test_returns_timing(self, sample_projections):
        timing = optimize_timing_only(
            "prof-1", sample_projections, 3000, 50000, 12,
        )
        assert isinstance(timing, TimingWindow)


class TestRecommendAmountOnly:
    def test_returns_range(self, sample_projections):
        amount = recommend_amount_only(
            "prof-1", sample_projections, 3000, "MEDIUM", 12, 9.0,
        )
        assert isinstance(amount, AmountRange)

    def test_very_high_risk_smaller(self, sample_projections):
        low = recommend_amount_only("p", sample_projections, 0, "LOW", 12, 9.0)
        very_high = recommend_amount_only("p", sample_projections, 0, "VERY_HIGH", 12, 9.0)
        assert very_high.max_amount < low.max_amount


# ---------------------------------------------------------------------------
# EMI / Principal conversion Tests
# ---------------------------------------------------------------------------
class TestFinancialMath:
    def test_emi_to_principal_round_trip(self):
        from services.guidance.app.domain.models import _emi_to_principal, _principal_to_emi
        principal = 100000
        rate = 9.0
        tenure = 24
        emi = _principal_to_emi(principal, rate, tenure)
        recovered = _emi_to_principal(emi, rate, tenure)
        assert abs(recovered - principal) < 1  # Within Rs 1

    def test_zero_rate_emi(self):
        from services.guidance.app.domain.models import _principal_to_emi
        emi = _principal_to_emi(120000, 0, 12)
        assert emi == 10000

    def test_zero_principal(self):
        from services.guidance.app.domain.models import _principal_to_emi
        assert _principal_to_emi(0, 9.0, 12) == 0

    def test_zero_tenure(self):
        from services.guidance.app.domain.models import _principal_to_emi
        assert _principal_to_emi(100000, 9.0, 0) == 0
