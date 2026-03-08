"""Feature engineering for the Risk Scoring model (XGBoost).

Computes 18 normalised features from raw profile + loan + external data.
Used by both the SageMaker training pipeline and local training scripts.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Feature definitions (canonical ordering for model input)
# ---------------------------------------------------------------------------

RISK_FEATURE_NAMES: list[str] = [
    "income_volatility_cv",
    "annual_income",
    "months_below_average",
    "debt_to_income_ratio",
    "total_outstanding",
    "active_loan_count",
    "credit_utilisation",
    "on_time_repayment_ratio",
    "has_defaults",
    "seasonal_variance",
    "crop_diversification_index",
    "weather_risk_score",
    "market_risk_score",
    "dependents",
    "age",
    "has_irrigation",
    "land_holding_acres",
    "soil_quality_score",
]

RISK_TARGET_REGRESSION = "risk_score"
RISK_TARGET_CLASSIFICATION = "risk_category"

CATEGORY_ENCODING = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "VERY_HIGH": 3}


# ---------------------------------------------------------------------------
# Feature extraction from raw data
# ---------------------------------------------------------------------------

def extract_risk_features(raw: dict[str, Any]) -> dict[str, float]:
    """Extract and normalise the 18 risk features from raw profile data.

    Handles missing values with sensible defaults for rural credit contexts.
    """
    return {
        "income_volatility_cv": min(float(raw.get("income_volatility_cv", 0.3)), 2.0),
        "annual_income": float(raw.get("annual_income", 60_000)),
        "months_below_average": min(int(raw.get("months_below_average", 0)), 12),
        "debt_to_income_ratio": min(float(raw.get("debt_to_income_ratio", 0.3)), 2.0),
        "total_outstanding": float(raw.get("total_outstanding", 0.0)),
        "active_loan_count": min(int(raw.get("active_loan_count", 0)), 10),
        "credit_utilisation": min(float(raw.get("credit_utilisation", 0.0)), 1.0),
        "on_time_repayment_ratio": max(0.0, min(1.0, float(raw.get("on_time_repayment_ratio", 1.0)))),
        "has_defaults": 1.0 if raw.get("has_defaults", False) else 0.0,
        "seasonal_variance": float(raw.get("seasonal_variance", 0.0)),
        "crop_diversification_index": max(0.0, min(1.0, float(raw.get("crop_diversification_index", 0.5)))),
        "weather_risk_score": max(0.0, min(100.0, float(raw.get("weather_risk_score", 0.0)))),
        "market_risk_score": max(0.0, min(100.0, float(raw.get("market_risk_score", 0.0)))),
        "dependents": min(int(raw.get("dependents", 0)), 12),
        "age": max(18, min(80, int(raw.get("age", 35)))),
        "has_irrigation": 1.0 if raw.get("has_irrigation", False) else 0.0,
        "land_holding_acres": max(0.0, float(raw.get("land_holding_acres", 2.0))),
        "soil_quality_score": max(0.0, min(100.0, float(raw.get("soil_quality_score", 50.0)))),
    }


def extract_risk_features_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised feature extraction for a DataFrame of profiles.

    Returns a DataFrame with only the 18 canonical features.
    """
    features = pd.DataFrame(index=df.index)

    features["income_volatility_cv"] = df.get("income_volatility_cv", 0.3).clip(0, 2.0)
    features["annual_income"] = df.get("annual_income", 60_000).clip(0)
    features["months_below_average"] = df.get("months_below_average", 0).clip(0, 12).astype(int)
    features["debt_to_income_ratio"] = df.get("debt_to_income_ratio", 0.3).clip(0, 2.0)
    features["total_outstanding"] = df.get("total_outstanding", 0).clip(0)
    features["active_loan_count"] = df.get("active_loan_count", 0).clip(0, 10).astype(int)
    features["credit_utilisation"] = df.get("credit_utilisation", 0).clip(0, 1.0)
    features["on_time_repayment_ratio"] = df.get("on_time_repayment_ratio", 1.0).clip(0, 1.0)
    features["has_defaults"] = df.get("has_defaults", False).astype(float)
    features["seasonal_variance"] = df.get("seasonal_variance", 0).clip(0)
    features["crop_diversification_index"] = df.get("crop_diversification_index", 0.5).clip(0, 1.0)
    features["weather_risk_score"] = df.get("weather_risk_score", 0).clip(0, 100)
    features["market_risk_score"] = df.get("market_risk_score", 0).clip(0, 100)
    features["dependents"] = df.get("dependents", 0).clip(0, 12).astype(int)
    features["age"] = df.get("age", 35).clip(18, 80).astype(int)
    features["has_irrigation"] = df.get("has_irrigation", False).astype(float)
    features["land_holding_acres"] = df.get("land_holding_acres", 2.0).clip(0, 50)
    features["soil_quality_score"] = df.get("soil_quality_score", 50).clip(0, 100)

    return features[RISK_FEATURE_NAMES]


def extract_risk_labels(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Extract regression (score) and classification (category) labels."""
    scores = df[RISK_TARGET_REGRESSION].clip(0, 1000).astype(int)
    categories = df[RISK_TARGET_CLASSIFICATION].map(CATEGORY_ENCODING).astype(int)
    return scores, categories


# ---------------------------------------------------------------------------
# Derived / interaction features for advanced models
# ---------------------------------------------------------------------------

def add_interaction_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add engineered interaction and non-linear features.

    These capture cross-factor effects the base XGBoost may learn
    but are explicit for interpretability and linear model baselines.
    """
    df = features.copy()

    # Log-transformed features (stabilise skewed distributions)
    df["log_annual_income"] = np.log1p(df["annual_income"])
    df["log_total_outstanding"] = np.log1p(df["total_outstanding"])
    df["log_seasonal_variance"] = np.log1p(df["seasonal_variance"])

    # Interaction: high DTI + volatile income = compounding risk
    df["dti_x_income_cv"] = df["debt_to_income_ratio"] * df["income_volatility_cv"]

    # Interaction: defaults + low on-time = severe repayment concern
    df["default_x_on_time"] = df["has_defaults"] * (1.0 - df["on_time_repayment_ratio"])

    # Irrigation mitigates seasonal risk
    df["irrigation_x_seasonal"] = df["has_irrigation"] * df["seasonal_variance"]

    # External risk compound
    df["external_risk_compound"] = (
        df["weather_risk_score"] / 100.0 * df["market_risk_score"] / 100.0
    )

    # Age risk (U-shaped: young and old are riskier)
    df["age_risk_u"] = ((df["age"] - 40).abs() / 30.0).clip(0, 1)

    # Land-income ratio (possible over-leveraging if income is low for land)
    df["income_per_acre"] = df["annual_income"] / df["land_holding_acres"].clip(lower=0.1)

    return df
