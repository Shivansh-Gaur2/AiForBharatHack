"""Feature engineering for Early Warning / Anomaly Detection models.

Computes 22 features from profile, loan, and cash-flow data
for the Isolation Forest (Phase A) and LightGBM severity classifier (Phase B).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Feature definitions (22 canonical features)
# ---------------------------------------------------------------------------

EARLY_WARNING_FEATURE_NAMES: list[str] = [
    "income_deviation_3m",
    "income_deviation_6m",
    "missed_payments_ytd",
    "days_overdue_avg",
    "dti_delta_3m",
    "surplus_trend_slope",
    "weather_shock_score",
    "market_price_shock",
    "crop_failure_probability",
    "loan_count_increase",
    "credit_utilisation_delta",
    "has_informal_debt",
    "seasonal_stress_flag",
    "risk_category_current",
    "repayment_months_remaining",
    "income_sources_count",
    "land_holding_acres",
    "has_irrigation",
    "household_size",
    "district_drought_index",
    "prev_alert_severity",
    "days_since_last_alert",
]

SEVERITY_ENCODING = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
RISK_CATEGORY_ENCODING = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}


# ---------------------------------------------------------------------------
# Feature extraction from aggregated data
# ---------------------------------------------------------------------------

def extract_early_warning_features(
    profile: dict[str, Any],
    cashflow_history: list[dict[str, float]],
    loan_data: dict[str, Any],
    alert_history: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    """Extract 22 early-warning features from multi-source data.

    Args:
        profile: Farmer profile with demographics and risk info.
        cashflow_history: Last 12+ months of {month, year, income, expense}.
        loan_data: Current loan exposure metrics.
        alert_history: Previous alerts (for lead-time features).
    """
    alert_history = alert_history or []

    # Income deviations
    incomes = [r.get("income", 0) for r in cashflow_history]
    if len(incomes) >= 6:
        avg_6m = np.mean(incomes[-6:])
        avg_all = np.mean(incomes) if incomes else 1
        income_dev_3m = (np.mean(incomes[-3:]) - avg_all) / max(avg_all, 1) * 100
        income_dev_6m = (avg_6m - avg_all) / max(avg_all, 1) * 100
    elif len(incomes) >= 3:
        avg_all = np.mean(incomes) if incomes else 1
        income_dev_3m = (np.mean(incomes[-3:]) - avg_all) / max(avg_all, 1) * 100
        income_dev_6m = income_dev_3m
    else:
        income_dev_3m = 0.0
        income_dev_6m = 0.0

    # Surplus trend
    nets = [r.get("income", 0) - r.get("expense", 0) for r in cashflow_history[-6:]]
    surplus_slope = _linear_slope(nets) if len(nets) >= 3 else 0.0

    # DTI delta
    current_dti = float(loan_data.get("debt_to_income_ratio", 0))
    prev_dti = float(loan_data.get("dti_3m_ago", current_dti))
    dti_delta = current_dti - prev_dti

    # Credit utilisation delta
    current_util = float(loan_data.get("credit_utilisation", 0))
    prev_util = float(loan_data.get("credit_utilisation_3m_ago", current_util))
    util_delta = current_util - prev_util

    # Alert history features
    if alert_history:
        last_alert = max(alert_history, key=lambda a: a.get("timestamp", 0))
        prev_severity = SEVERITY_ENCODING.get(last_alert.get("severity", "INFO"), 0)
        days_since = int(last_alert.get("days_since", 365))
    else:
        prev_severity = 0
        days_since = 365

    # Seasonal stress: lean months for rainfed farmers
    current_month = int(profile.get("current_month", 1))
    is_lean = current_month in (5, 6, 7) and not profile.get("has_irrigation", False)

    return {
        "income_deviation_3m": round(income_dev_3m, 2),
        "income_deviation_6m": round(income_dev_6m, 2),
        "missed_payments_ytd": int(loan_data.get("missed_payments", 0)),
        "days_overdue_avg": float(loan_data.get("days_overdue_avg", 0)),
        "dti_delta_3m": round(dti_delta, 4),
        "surplus_trend_slope": round(surplus_slope, 2),
        "weather_shock_score": float(profile.get("weather_risk_score", 0)),
        "market_price_shock": float(profile.get("market_risk_score", 0)),
        "crop_failure_probability": float(profile.get("crop_failure_prob", 0)),
        "loan_count_increase": int(loan_data.get("new_loans_6m", 0)),
        "credit_utilisation_delta": round(util_delta, 4),
        "has_informal_debt": 1.0 if profile.get("has_informal_debt", False) else 0.0,
        "seasonal_stress_flag": 1.0 if is_lean else 0.0,
        "risk_category_current": RISK_CATEGORY_ENCODING.get(
            profile.get("risk_category", "MEDIUM"), 1
        ),
        "repayment_months_remaining": int(loan_data.get("months_remaining", 12)),
        "income_sources_count": int(profile.get("income_sources", 1)),
        "land_holding_acres": float(profile.get("land_holding_acres", 2.0)),
        "has_irrigation": 1.0 if profile.get("has_irrigation", False) else 0.0,
        "household_size": int(profile.get("household_size", 4)),
        "district_drought_index": float(profile.get("district_drought_index", 0)),
        "prev_alert_severity": prev_severity,
        "days_since_last_alert": min(days_since, 365),
    }


def extract_early_warning_features_batch(
    events_df: pd.DataFrame,
) -> pd.DataFrame:
    """Vectorised feature extraction from a pre-computed events DataFrame.

    Expects columns matching the synthetic generator output.
    Returns only the 22 canonical features.
    """
    df = events_df.copy()

    # Map available columns; fill missing with defaults
    feature_map = {
        "income_deviation_3m": df.get("income_deviation_3m", 0),
        "income_deviation_6m": df.get("income_deviation_3m", 0) * 0.8,  # approximate
        "missed_payments_ytd": df.get("missed_payments", 0),
        "days_overdue_avg": df.get("days_overdue_avg", 0),
        "dti_delta_3m": 0.0,
        "surplus_trend_slope": df.get("surplus_trend_slope", 0),
        "weather_shock_score": df.get("weather_risk_score", 0),
        "market_price_shock": df.get("market_risk_score", 0),
        "crop_failure_probability": 0.0,
        "loan_count_increase": 0,
        "credit_utilisation_delta": 0.0,
        "has_informal_debt": 0.0,
        "seasonal_stress_flag": df["month"].isin([5, 6, 7]).astype(float) * (1 - df.get("has_irrigation", 0).astype(float)),
        "risk_category_current": df.get("risk_category", "MEDIUM").map(RISK_CATEGORY_ENCODING).fillna(1),
        "repayment_months_remaining": 12,
        "income_sources_count": 1,
        "land_holding_acres": 2.0,
        "has_irrigation": df.get("has_irrigation", False).astype(float),
        "household_size": 4,
        "district_drought_index": 0.0,
        "prev_alert_severity": 0,
        "days_since_last_alert": 365,
    }

    result = pd.DataFrame(feature_map, index=df.index)
    return result[EARLY_WARNING_FEATURE_NAMES]


def extract_severity_labels(df: pd.DataFrame) -> pd.Series:
    """Extract encoded severity labels."""
    return df["severity"].map(SEVERITY_ENCODING).astype(int)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = np.mean(values)
    num = np.sum((x - x_mean) * (np.array(values) - y_mean))
    den = np.sum((x - x_mean) ** 2)
    return float(num / den) if den != 0 else 0.0
