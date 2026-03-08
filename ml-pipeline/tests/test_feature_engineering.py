"""Tests for ML Pipeline — Feature Engineering.

Validates the 3 feature extraction modules produce correct dimensions,
handle missing data, and maintain canonical ordering.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_risk_profile() -> dict[str, Any]:
    return {
        "income_volatility_cv": 0.35,
        "annual_income": 120_000,
        "months_below_average": 3,
        "debt_to_income_ratio": 0.45,
        "total_outstanding": 50_000,
        "active_loan_count": 2,
        "credit_utilisation": 0.6,
        "on_time_repayment_ratio": 0.85,
        "has_defaults": False,
        "seasonal_variance": 5000,
        "crop_diversification_index": 0.7,
        "weather_risk_score": 25,
        "market_risk_score": 15,
        "dependents": 3,
        "age": 35,
        "has_irrigation": True,
        "land_holding_acres": 2.5,
        "soil_quality_score": 0.65,
        "risk_score": 420,
        "risk_category": "MEDIUM",
    }


@pytest.fixture()
def sample_cashflow_records() -> pd.DataFrame:
    """24-month income/expense history."""
    np.random.seed(42)
    months = pd.date_range("2023-01-01", periods=24, freq="MS")
    return pd.DataFrame(
        {
            "year": [d.year for d in months],
            "month": [d.month for d in months],
            "monthly_income": np.random.lognormal(10, 0.3, 24).astype(float),
            "monthly_expense": np.random.lognormal(9.5, 0.2, 24).astype(float),
            "profile_id": "P001",
            "crop_type": "rice",
            "district": "varanasi",
            "irrigation_type": "canal",
            "weather_index": np.random.uniform(0.5, 1.0, 24),
            "msp_deviation": np.random.uniform(-0.1, 0.1, 24),
            "diesel_price_index": np.random.uniform(0.9, 1.1, 24),
        }
    )


@pytest.fixture()
def sample_warning_data() -> tuple[dict, list, dict, list]:
    profile = {
        "income_volatility_cv": 0.4,
        "annual_income": 80_000,
        "dependents": 4,
        "has_irrigation": False,
        "land_holding_acres": 1.5,
        "district_drought_index": 0.7,
        "income_sources_count": 1,
        "household_size": 6,
        "risk_category": "HIGH",
        "has_informal_debt": True,
    }
    cashflow_history = [
        {"monthly_income": 8000 - i * 200, "monthly_expense": 7000}
        for i in range(12)
    ]
    loan_data = {
        "emi_amount": 2000,
        "missed_payments_ytd": 2,
        "days_overdue_avg": 15,
        "active_loan_count": 3,
        "credit_utilisation": 0.8,
        "repayment_months_remaining": 18,
    }
    alert_history = [
        {"severity": "WARNING", "created_at": "2024-01-15"},
    ]
    return profile, cashflow_history, loan_data, alert_history


# ---------------------------------------------------------------------------
# Risk features
# ---------------------------------------------------------------------------


class TestRiskFeatures:
    def test_extract_produces_18_features(self, sample_risk_profile: dict):
        from data.feature_engineering.risk_features import (
            RISK_FEATURE_NAMES,
            extract_risk_features,
        )

        features = extract_risk_features(sample_risk_profile)
        assert len(features) == 18
        for name in RISK_FEATURE_NAMES:
            assert name in features

    def test_extract_handles_empty_dict(self):
        from data.feature_engineering.risk_features import (
            RISK_FEATURE_NAMES,
            extract_risk_features,
        )

        features = extract_risk_features({})
        assert len(features) == 18
        # All values should be finite
        for v in features.values():
            assert math.isfinite(v)

    def test_batch_extraction_shape(self, sample_risk_profile: dict):
        from data.feature_engineering.risk_features import (
            RISK_FEATURE_NAMES,
            extract_risk_features_batch,
        )

        batch = pd.DataFrame([sample_risk_profile] * 10)
        df = extract_risk_features_batch(batch)
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (10, 18)
        assert list(df.columns) == RISK_FEATURE_NAMES

    def test_interaction_features(self, sample_risk_profile: dict):
        from data.feature_engineering.risk_features import (
            add_interaction_features,
            extract_risk_features_batch,
        )

        batch = pd.DataFrame([sample_risk_profile] * 5)
        df = extract_risk_features_batch(batch)
        df_enriched = add_interaction_features(df)
        # 18 base + 9 interaction features = 27
        assert df_enriched.shape[1] >= 27

    def test_category_encoding(self):
        from data.feature_engineering.risk_features import CATEGORY_ENCODING

        assert CATEGORY_ENCODING == {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}

    def test_clipping_bounds(self):
        from data.feature_engineering.risk_features import extract_risk_features

        extreme = {"income_volatility_cv": 10.0, "debt_to_income_ratio": 5.0}
        feat = extract_risk_features(extreme)
        assert feat["income_volatility_cv"] <= 2.0
        assert feat["debt_to_income_ratio"] <= 2.0


# ---------------------------------------------------------------------------
# Cashflow features
# ---------------------------------------------------------------------------


class TestCashflowFeatures:
    def test_prepare_prophet_dataframe(self, sample_cashflow_records: pd.DataFrame):
        from data.feature_engineering.cashflow_features import (
            prepare_prophet_dataframe,
        )

        df = prepare_prophet_dataframe(sample_cashflow_records)
        assert "ds" in df.columns
        assert "y" in df.columns
        # Season flags should be present
        for col in ["is_kharif", "is_rabi", "is_zaid"]:
            assert col in df.columns
        assert len(df) == 24

    def test_season_flags_correct(self):
        from data.feature_engineering.cashflow_features import (
            _month_to_season_flags,
        )

        # June–October = Kharif
        assert _month_to_season_flags(6) == (1, 0, 0)
        assert _month_to_season_flags(10) == (1, 0, 0)
        # November–March = Rabi
        assert _month_to_season_flags(11) == (0, 1, 0)
        assert _month_to_season_flags(1) == (0, 1, 0)
        # April–May = Zaid
        assert _month_to_season_flags(4) == (0, 0, 1)
        assert _month_to_season_flags(5) == (0, 0, 1)

    def test_feature_matrix_has_lag_columns(self, sample_cashflow_records: pd.DataFrame):
        from data.feature_engineering.cashflow_features import (
            CASHFLOW_FEATURE_NAMES,
            build_cashflow_feature_matrix,
        )

        mat = build_cashflow_feature_matrix(sample_cashflow_records)
        for col in ["income_lag_1", "income_lag_3", "income_rolling_mean_3"]:
            assert col in mat.columns

    def test_cluster_profiles(self, sample_cashflow_records: pd.DataFrame):
        from data.feature_engineering.cashflow_features import (
            compute_cluster_profiles,
        )

        # Build a profiles DataFrame with required columns
        profiles = pd.DataFrame({
            "profile_id": [f"P{i:03d}" for i in range(30)],
            "primary_crop": np.random.choice(["rice", "wheat", "maize"], 30),
            "district": np.random.choice(["varanasi", "lucknow", "patna"], 30),
            "has_irrigation": np.random.choice([True, False], 30),
        })
        clusters = compute_cluster_profiles(profiles, sample_cashflow_records, n_clusters=3)
        assert "cluster_id" in clusters.columns


# ---------------------------------------------------------------------------
# Early Warning features
# ---------------------------------------------------------------------------


class TestEarlyWarningFeatures:
    def test_extract_produces_22_features(self, sample_warning_data):
        from data.feature_engineering.early_warning_features import (
            EARLY_WARNING_FEATURE_NAMES,
            extract_early_warning_features,
        )

        profile, cashflow, loan, alerts = sample_warning_data
        features = extract_early_warning_features(profile, cashflow, loan, alerts)
        assert len(features) == 22
        for name in EARLY_WARNING_FEATURE_NAMES:
            assert name in features

    def test_extract_handles_empty_inputs(self):
        from data.feature_engineering.early_warning_features import (
            extract_early_warning_features,
        )

        features = extract_early_warning_features({}, [], {}, [])
        assert len(features) == 22
        for v in features.values():
            assert math.isfinite(v)

    def test_batch_extraction_shape(self, sample_warning_data):
        from data.feature_engineering.early_warning_features import (
            extract_early_warning_features_batch,
        )

        # Build a DataFrame with columns the batch function expects
        rng = np.random.default_rng(42)
        n = 20
        events_df = pd.DataFrame({
            "month": rng.integers(1, 13, n),
            "income_deviation_3m": rng.normal(0, 0.2, n),
            "missed_payments": rng.integers(0, 4, n),
            "days_overdue_avg": rng.uniform(0, 30, n),
            "surplus_trend_slope": rng.normal(0, 100, n),
            "weather_risk_score": rng.uniform(0, 50, n),
            "market_risk_score": rng.uniform(0, 50, n),
            "has_irrigation": rng.choice([0, 1], n),
            "risk_category": rng.choice(["LOW", "MEDIUM", "HIGH"], n),
        })
        df = extract_early_warning_features_batch(events_df)
        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] == n
        assert df.shape[1] == 22

    def test_severity_labels(self, sample_warning_data):
        from data.feature_engineering.early_warning_features import (
            SEVERITY_ENCODING,
            extract_severity_labels,
        )

        # Build DataFrame with known severity labels
        records = pd.DataFrame({"severity": ["INFO", "WARNING", "CRITICAL"]})
        labels = extract_severity_labels(records)
        assert list(labels) == [0, 1, 2]

    def test_surplus_trend_slope(self, sample_warning_data):
        from data.feature_engineering.early_warning_features import (
            extract_early_warning_features,
        )

        profile, cashflow, loan, alerts = sample_warning_data
        features = extract_early_warning_features(profile, cashflow, loan, alerts)
        # Decreasing income → negative slope
        assert features["surplus_trend_slope"] <= 0
