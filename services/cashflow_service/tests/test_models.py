"""Unit tests for Cash Flow domain models — seasonal analysis, projections,
repayment capacity, timing alignment, and forecast builder.

Tests follow the same patterns as loan_tracker & risk_assessment services.
"""

from __future__ import annotations

import pytest

from services.cashflow_service.app.domain.models import (
    CashFlowCategory,
    CashFlowForecast,
    CashFlowRecord,
    FlowDirection,
    ForecastConfidence,
    MonthlyProjection,
    _month_to_season,
    analyse_seasonal_patterns,
    build_forecast,
    compute_repayment_capacity,
    compute_timing_windows,
    compute_uncertainty_bands,
    generate_projections,
)
from services.shared.models import Season


# ---------------------------------------------------------------------------
# Helpers: sample data
# ---------------------------------------------------------------------------
def _make_records() -> list[CashFlowRecord]:
    """Create a realistic 2-year set of records for a rice farmer."""
    records: list[CashFlowRecord] = []
    for year in (2024, 2025):
        # Kharif crop income: big in Oct-Nov
        for m, amt in [(10, 80000), (11, 50000)]:
            records.append(CashFlowRecord(
                record_id=f"inc-kharif-{year}-{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=amt, month=m, year=year,
                season=Season.KHARIF,
            ))
        # Rabi crop income: in Mar-Apr
        for m, amt in [(3, 60000), (4, 30000)]:
            records.append(CashFlowRecord(
                record_id=f"inc-rabi-{year}-{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=amt, month=m, year=year,
                season=Season.RABI,
            ))
        # Labour income year-round
        for m in range(1, 13):
            records.append(CashFlowRecord(
                record_id=f"inc-labour-{year}-{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.LABOUR_INCOME,
                direction=FlowDirection.INFLOW,
                amount=8000, month=m, year=year,
            ))
        # Household expense year-round
        for m in range(1, 13):
            records.append(CashFlowRecord(
                record_id=f"exp-house-{year}-{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.HOUSEHOLD,
                direction=FlowDirection.OUTFLOW,
                amount=6000, month=m, year=year,
            ))
        # Seed/fertilizer expense (Jun, Jul)
        for m, amt in [(6, 15000), (7, 10000)]:
            records.append(CashFlowRecord(
                record_id=f"exp-seed-{year}-{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.SEED_FERTILIZER,
                direction=FlowDirection.OUTFLOW,
                amount=amt, month=m, year=year,
            ))
    return records


# ---------------------------------------------------------------------------
# Tests: Seasonal Analysis
# ---------------------------------------------------------------------------
class TestSeasonalAnalysis:
    def test_discovers_patterns_from_records(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        assert len(patterns) >= 3  # crop income, labour income, household, seed

    def test_identifies_peak_months(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        crop_patterns = [
            p for p in patterns
            if p.category == CashFlowCategory.CROP_INCOME
        ]
        assert len(crop_patterns) == 1
        # Crop income peak should be October (highest: 80k)
        assert crop_patterns[0].peak_month == 10

    def test_computes_variability(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        # Labour income has zero variability (same amount every month)
        labour = [
            p for p in patterns
            if p.category == CashFlowCategory.LABOUR_INCOME
        ]
        assert len(labour) == 1
        assert labour[0].variability_cv == 0.0

    def test_identifies_correct_seasons(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        crop = [
            p for p in patterns
            if p.category == CashFlowCategory.CROP_INCOME
        ]
        # Peak month 10 → KHARIF
        assert crop[0].season == Season.KHARIF

    def test_groups_by_direction(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        inflows = [p for p in patterns if p.direction == FlowDirection.INFLOW]
        outflows = [p for p in patterns if p.direction == FlowDirection.OUTFLOW]
        assert len(inflows) >= 2
        assert len(outflows) >= 1

    def test_empty_records_returns_empty(self):
        patterns = analyse_seasonal_patterns([])
        assert patterns == []


class TestMonthToSeason:
    def test_kharif_months(self):
        for m in (6, 7, 8, 9, 10):
            assert _month_to_season(m) == Season.KHARIF

    def test_rabi_months(self):
        for m in (11, 12, 1, 2, 3):
            assert _month_to_season(m) == Season.RABI

    def test_zaid_months(self):
        for m in (4, 5):
            assert _month_to_season(m) == Season.ZAID


# ---------------------------------------------------------------------------
# Tests: Projections
# ---------------------------------------------------------------------------
class TestProjections:
    def test_generates_correct_number_of_months(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 12, 1, 2026)
        assert len(projections) == 12

    def test_months_wrap_correctly(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 15, 10, 2026)
        assert projections[0].month == 10
        assert projections[0].year == 2026
        assert projections[3].month == 1
        assert projections[3].year == 2027

    def test_inflow_outflow_match_patterns(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 12, 1, 2026)
        # October should have high inflow (crop income peak)
        oct_proj = next(p for p in projections if p.month == 10)
        jan_proj = next(p for p in projections if p.month == 1)
        assert oct_proj.projected_inflow > jan_proj.projected_inflow

    def test_weather_adjustment_scales_inflow(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        normal = generate_projections(patterns, 12, 1, 2026, weather_adjustment=1.0)
        drought = generate_projections(patterns, 12, 1, 2026, weather_adjustment=0.7)
        # Total inflow should be lower in drought scenario
        normal_inflow = sum(p.projected_inflow for p in normal)
        drought_inflow = sum(p.projected_inflow for p in drought)
        assert drought_inflow < normal_inflow

    def test_market_adjustment_scales_inflow(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        normal = generate_projections(patterns, 12, 1, 2026, market_adjustment=1.0)
        boom = generate_projections(patterns, 12, 1, 2026, market_adjustment=1.3)
        normal_inflow = sum(p.projected_inflow for p in normal)
        boom_inflow = sum(p.projected_inflow for p in boom)
        assert boom_inflow > normal_inflow

    def test_net_cash_flow_computed(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 12, 1, 2026)
        for p in projections:
            assert p.net_cash_flow == pytest.approx(
                p.projected_inflow - p.projected_outflow, abs=0.02,
            )


# ---------------------------------------------------------------------------
# Tests: Uncertainty Bands
# ---------------------------------------------------------------------------
class TestUncertaintyBands:
    def test_correct_count(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 12, 1, 2026)
        bands = compute_uncertainty_bands(projections, patterns)
        assert len(bands) == 12

    def test_bands_ordered_correctly(self):
        records = _make_records()
        patterns = analyse_seasonal_patterns(records)
        projections = generate_projections(patterns, 6, 1, 2026)
        bands = compute_uncertainty_bands(projections, patterns)
        for band in bands:
            assert band.lower_bound <= band.expected <= band.upper_bound


# ---------------------------------------------------------------------------
# Tests: Repayment Capacity
# ---------------------------------------------------------------------------
class TestRepaymentCapacity:
    def test_positive_surplus(self):
        projections = [
            MonthlyProjection(m, 2026, 20000, 10000, 10000, ForecastConfidence.HIGH)
            for m in range(1, 13)
        ]
        cap = compute_repayment_capacity("test", projections)
        assert cap.monthly_surplus_avg == 10000.0
        assert cap.monthly_surplus_min == 10000.0
        assert cap.max_affordable_emi == 6000.0    # 60% of min
        assert cap.recommended_emi == 4000.0       # 40% of avg

    def test_variable_surplus(self):
        projections = [
            MonthlyProjection(1, 2026, 30000, 10000, 20000, ForecastConfidence.HIGH),
            MonthlyProjection(2, 2026, 12000, 10000, 2000, ForecastConfidence.MEDIUM),
            MonthlyProjection(3, 2026, 25000, 10000, 15000, ForecastConfidence.HIGH),
        ]
        cap = compute_repayment_capacity("test", projections)
        assert cap.monthly_surplus_min == 2000.0
        assert cap.max_affordable_emi == 1200.0     # 60% of 2000

    def test_emergency_reserve(self):
        projections = [
            MonthlyProjection(m, 2026, 20000, 10000, 10000, ForecastConfidence.HIGH)
            for m in range(1, 13)
        ]
        cap = compute_repayment_capacity("test", projections, household_monthly_expense=6000)
        assert cap.emergency_reserve == 18000.0  # 3 × 6000

    def test_dscr_with_obligations(self):
        projections = [
            MonthlyProjection(m, 2026, 20000, 10000, 10000, ForecastConfidence.HIGH)
            for m in range(1, 13)
        ]
        cap = compute_repayment_capacity(
            "test", projections, existing_monthly_obligations=5000,
        )
        assert cap.debt_service_coverage_ratio == 2.0  # 10000/5000

    def test_empty_projections(self):
        cap = compute_repayment_capacity("test", [])
        assert cap.monthly_surplus_avg == 0.0
        assert cap.recommended_emi == 0.0

    def test_negative_surplus_caps_emi_at_zero(self):
        projections = [
            MonthlyProjection(1, 2026, 5000, 10000, -5000, ForecastConfidence.LOW),
        ]
        cap = compute_repayment_capacity("test", projections)
        assert cap.max_affordable_emi == 0.0
        assert cap.recommended_emi == 0.0


# ---------------------------------------------------------------------------
# Tests: Timing Windows
# ---------------------------------------------------------------------------
class TestTimingWindows:
    def test_generates_windows(self):
        projections = [
            MonthlyProjection(m, 2026, 15000, 10000, 5000, ForecastConfidence.HIGH)
            for m in range(1, 13)
        ]
        windows = compute_timing_windows(projections, loan_tenure_months=6)
        assert len(windows) == 7  # 12 - 6 + 1

    def test_best_window_has_highest_score(self):
        projections = []
        # First 6 months: low surplus
        for m in range(1, 7):
            projections.append(
                MonthlyProjection(m, 2026, 10000, 9000, 1000, ForecastConfidence.MEDIUM)
            )
        # Last 6 months: high surplus
        for m in range(7, 13):
            projections.append(
                MonthlyProjection(m, 2026, 30000, 10000, 20000, ForecastConfidence.HIGH)
            )
        windows = compute_timing_windows(projections, loan_tenure_months=6)
        best = max(windows, key=lambda w: w.suitability_score)
        # Best window should start in or after month 7
        assert best.start_month >= 7

    def test_empty_projections_returns_empty(self):
        assert compute_timing_windows([], 6) == []

    def test_horizon_shorter_than_tenure(self):
        projections = [
            MonthlyProjection(1, 2026, 15000, 10000, 5000, ForecastConfidence.HIGH),
            MonthlyProjection(2, 2026, 15000, 10000, 5000, ForecastConfidence.HIGH),
        ]
        windows = compute_timing_windows(projections, loan_tenure_months=12)
        assert len(windows) == 1  # fallback: whole horizon


# ---------------------------------------------------------------------------
# Tests: Forecast Builder
# ---------------------------------------------------------------------------
class TestBuildForecast:
    def test_builds_complete_forecast(self):
        records = _make_records()
        forecast = build_forecast(
            profile_id="farmer-001",
            records=records,
            horizon_months=12,
            start_month=1,
            start_year=2026,
        )
        assert isinstance(forecast, CashFlowForecast)
        assert forecast.profile_id == "farmer-001"
        assert len(forecast.monthly_projections) == 12
        assert len(forecast.seasonal_patterns) >= 3
        assert len(forecast.uncertainty_bands) == 12
        assert len(forecast.assumptions) >= 1
        assert forecast.repayment_capacity is not None
        assert len(forecast.timing_windows) >= 1
        assert forecast.forecast_id

    def test_forecast_with_weather_adjustment(self):
        records = _make_records()
        normal = build_forecast("farmer-001", records, 12, 1, 2026, weather_adjustment=1.0)
        drought = build_forecast("farmer-001", records, 12, 1, 2026, weather_adjustment=0.6)
        assert drought.get_total_projected_inflow() < normal.get_total_projected_inflow()

    def test_forecast_with_market_adjustment(self):
        records = _make_records()
        normal = build_forecast("farmer-001", records, 12, 1, 2026, market_adjustment=1.0)
        boom = build_forecast("farmer-001", records, 12, 1, 2026, market_adjustment=1.4)
        assert boom.get_total_projected_inflow() > normal.get_total_projected_inflow()

    def test_assumptions_reflect_adjustments(self):
        records = _make_records()
        forecast = build_forecast(
            "farmer-001", records, 12, 1, 2026,
            weather_adjustment=0.8, market_adjustment=1.2,
        )
        factors = [a.factor for a in forecast.assumptions]
        assert "Weather" in factors
        assert "Market" in factors

    def test_default_assumptions(self):
        records = _make_records()
        forecast = build_forecast("farmer-001", records, 12, 1, 2026)
        assert len(forecast.assumptions) == 1
        assert forecast.assumptions[0].factor == "Baseline"

    def test_get_best_timing_window(self):
        records = _make_records()
        forecast = build_forecast("farmer-001", records, 12, 1, 2026)
        best = forecast.get_best_timing_window()
        assert best is not None
        assert 0 <= best.suitability_score <= 100

    def test_get_worst_month(self):
        records = _make_records()
        forecast = build_forecast("farmer-001", records, 12, 1, 2026)
        worst = forecast.get_worst_month()
        assert worst is not None
        # Worst month should have lowest net cash flow
        assert all(
            worst.net_cash_flow <= p.net_cash_flow
            for p in forecast.monthly_projections
        )

    def test_get_total_inflow_outflow(self):
        records = _make_records()
        forecast = build_forecast("farmer-001", records, 12, 1, 2026)
        assert forecast.get_total_projected_inflow() > 0
        assert forecast.get_total_projected_outflow() > 0


# ---------------------------------------------------------------------------
# Tests: MonthlyProjection properties
# ---------------------------------------------------------------------------
class TestMonthlyProjection:
    def test_surplus_ratio_positive(self):
        p = MonthlyProjection(1, 2026, 20000, 10000, 10000, ForecastConfidence.HIGH)
        assert p.surplus_ratio == 0.5

    def test_surplus_ratio_zero_inflow(self):
        p = MonthlyProjection(1, 2026, 0, 5000, -5000, ForecastConfidence.LOW)
        assert p.surplus_ratio == 0.0

    def test_surplus_ratio_negative(self):
        p = MonthlyProjection(1, 2026, 10000, 15000, -5000, ForecastConfidence.MEDIUM)
        assert p.surplus_ratio == -0.5
