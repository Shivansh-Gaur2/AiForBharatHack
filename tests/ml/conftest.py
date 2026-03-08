"""Shared fixtures for ML unit & integration tests."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Canonical feature dicts shared across test modules
# ---------------------------------------------------------------------------

@pytest.fixture
def safe_risk_features() -> dict:
    """Low-risk farmer — expects LOW or MEDIUM prediction."""
    return {
        "income_volatility_cv":       0.10,
        "annual_income":              360000,
        "months_below_average":       1,
        "debt_to_income_ratio":       0.15,
        "total_outstanding":          30000,
        "active_loan_count":          1,
        "credit_utilisation":         0.20,
        "on_time_repayment_ratio":    0.97,
        "has_defaults":               0,
        "seasonal_variance":          15,
        "crop_diversification_index": 0.80,
        "weather_risk_score":         10,
        "market_risk_score":          10,
        "dependents":                 2,
        "age":                        35,
        "has_irrigation":             1,
        "land_holding_acres":         4.0,
        "soil_quality_score":         75,
    }


@pytest.fixture
def stressed_risk_features() -> dict:
    """Very-high-risk farmer — expects HIGH or VERY_HIGH prediction."""
    return {
        "income_volatility_cv":       0.70,
        "annual_income":              80000,
        "months_below_average":       8,
        "debt_to_income_ratio":       0.90,
        "total_outstanding":          120000,
        "active_loan_count":          4,
        "credit_utilisation":         0.90,
        "on_time_repayment_ratio":    0.40,
        "has_defaults":               1,
        "seasonal_variance":          65,
        "crop_diversification_index": 0.10,
        "weather_risk_score":         70,
        "market_risk_score":          65,
        "dependents":                 6,
        "age":                        50,
        "has_irrigation":             0,
        "land_holding_acres":         1.0,
        "soil_quality_score":         30,
    }


@pytest.fixture
def safe_ew_features() -> dict:
    """Normal borrower — expects INFO or at most WARNING."""
    return {
        "income_deviation_3m":  5.0,
        "income_deviation_6m":  2.0,
        "missed_payments_ytd":  0,
        "days_overdue_avg":     0.0,
        "dti_ratio":            0.20,
        "dti_delta_3m":         0.01,
        "surplus_trend_slope":  500.0,
        "weather_shock_score":  5.0,
        "market_price_shock":   2.0,
        "seasonal_stress_flag": 0,
        "risk_category_current": 0,
        "days_since_last_alert": 90,
    }


@pytest.fixture
def critical_ew_features() -> dict:
    """Severely stressed borrower — expects CRITICAL."""
    return {
        "income_deviation_3m":  -50.0,
        "income_deviation_6m":  -40.0,
        "missed_payments_ytd":  5,
        "days_overdue_avg":     60.0,
        "dti_ratio":            0.95,
        "dti_delta_3m":         0.20,
        "surplus_trend_slope":  -1200.0,
        "weather_shock_score":  75.0,
        "market_price_shock":   -35.0,
        "seasonal_stress_flag": 1,
        "risk_category_current": 3,
        "days_since_last_alert": 7,
    }
