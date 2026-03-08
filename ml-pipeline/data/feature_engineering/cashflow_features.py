"""Feature engineering for Cash Flow Prediction (Prophet / LSTM).

Builds time-series feature matrices from monthly income/expense records
with external regressors (weather, market, seasonal indicators).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Feature definitions
# ---------------------------------------------------------------------------

CASHFLOW_FEATURE_NAMES: list[str] = [
    "monthly_income",
    "monthly_expense",
    "net_cashflow",
    "income_lag_1",
    "income_lag_2",
    "income_lag_3",
    "income_lag_6",
    "income_lag_12",
    "expense_lag_1",
    "income_rolling_mean_3",
    "income_rolling_std_3",
    "income_rolling_mean_6",
    "month_sin",
    "month_cos",
    "is_kharif",
    "is_rabi",
    "is_zaid",
    "weather_index",
    "msp_deviation",
    "diesel_price_index",
]


def _month_to_season_flags(month: int) -> tuple[int, int, int]:
    """Return (is_kharif, is_rabi, is_zaid) flags."""
    if month in (6, 7, 8, 9, 10):
        return (1, 0, 0)
    elif month in (11, 12, 1, 2, 3):
        return (0, 1, 0)
    return (0, 0, 1)


# ---------------------------------------------------------------------------
# Prophet-specific formatting
# ---------------------------------------------------------------------------

def prepare_prophet_dataframe(
    records: pd.DataFrame,
    profile_id: str | None = None,
) -> pd.DataFrame:
    """Convert monthly records into Prophet-compatible DataFrame.

    Prophet requires columns: ds (datetime), y (target).
    External regressors are added as additional columns.
    """
    if profile_id is not None:
        records = records[records["profile_id"] == profile_id].copy()

    df = records.copy()
    df["ds"] = pd.to_datetime(
        df.apply(lambda r: f"{int(r['year'])}-{int(r['month']):02d}-15", axis=1)
    )
    df["y"] = df["monthly_income"]
    df = df.sort_values("ds").reset_index(drop=True)

    # Fourier-encoded month
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # Season flags
    seasons = df["month"].apply(_month_to_season_flags)
    df["is_kharif"] = seasons.apply(lambda x: x[0])
    df["is_rabi"] = seasons.apply(lambda x: x[1])
    df["is_zaid"] = seasons.apply(lambda x: x[2])

    # External regressors (defaults if not present)
    if "weather_index" not in df.columns:
        df["weather_index"] = 0.0
    if "msp_deviation" not in df.columns:
        df["msp_deviation"] = 0.0
    if "diesel_price_index" not in df.columns:
        df["diesel_price_index"] = 0.0

    return df


# ---------------------------------------------------------------------------
# LSTM / tabular feature matrix
# ---------------------------------------------------------------------------

def build_cashflow_feature_matrix(
    records: pd.DataFrame,
    profile_id: str | None = None,
) -> pd.DataFrame:
    """Build time-series feature matrix with lag features and rolling statistics.

    Used for LSTM and tabular models.
    """
    if profile_id is not None:
        records = records[records["profile_id"] == profile_id].copy()

    df = records.sort_values(["year", "month"]).copy()

    # Lag features
    for lag in [1, 2, 3, 6, 12]:
        df[f"income_lag_{lag}"] = df["monthly_income"].shift(lag)
    df["expense_lag_1"] = df["monthly_expense"].shift(1)

    # Rolling statistics
    df["income_rolling_mean_3"] = df["monthly_income"].rolling(3, min_periods=1).mean()
    df["income_rolling_std_3"] = df["monthly_income"].rolling(3, min_periods=1).std().fillna(0)
    df["income_rolling_mean_6"] = df["monthly_income"].rolling(6, min_periods=1).mean()

    # Fourier-encoded month
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # Season one-hot
    seasons = df["month"].apply(_month_to_season_flags)
    df["is_kharif"] = seasons.apply(lambda x: x[0])
    df["is_rabi"] = seasons.apply(lambda x: x[1])
    df["is_zaid"] = seasons.apply(lambda x: x[2])

    # External regressors (defaults if not present)
    for col in ["weather_index", "msp_deviation", "diesel_price_index"]:
        if col not in df.columns:
            df[col] = 0.0

    # Drop initial rows where lag features are NaN
    df = df.dropna(subset=["income_lag_12"]).reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Cluster-level features (for Prophet cluster training)
# ---------------------------------------------------------------------------

def compute_cluster_profiles(
    profiles: pd.DataFrame,
    cashflows: pd.DataFrame,
    n_clusters: int = 20,
) -> pd.DataFrame:
    """Cluster farmers by crop + district for Prophet cluster models.

    Returns a DataFrame with cluster_id assigned to each profile.
    """
    from sklearn.preprocessing import LabelEncoder

    df = profiles[["profile_id", "primary_crop", "district", "has_irrigation"]].copy()

    le_crop = LabelEncoder()
    le_dist = LabelEncoder()
    df["crop_enc"] = le_crop.fit_transform(df["primary_crop"].fillna("other"))
    df["dist_enc"] = le_dist.fit_transform(df["district"].fillna("other"))
    df["irrigation_enc"] = df["has_irrigation"].astype(int)

    from sklearn.cluster import KMeans

    X = df[["crop_enc", "dist_enc", "irrigation_enc"]].values
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster_id"] = kmeans.fit_predict(X)

    return df[["profile_id", "cluster_id"]]
