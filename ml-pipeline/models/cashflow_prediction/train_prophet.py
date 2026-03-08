"""Prophet cash-flow prediction – SageMaker training entry-point.

Trains per-cluster Prophet models with Kharif/Rabi/Zaid regressors
and external signals (weather_index, msp_deviation, diesel_price_index).

Model artefact: one serialised Prophet model per cluster + cluster mapping.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import pickle
from typing import Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
INPUT_DIR = os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "changepoint_prior_scale": 0.1,
    "seasonality_prior_scale": 10.0,
    "holidays_prior_scale": 10.0,
    "changepoint_range": 0.85,
    "n_changepoints": 25,
    "yearly_seasonality": True,
    "weekly_seasonality": False,
    "daily_seasonality": False,
    "forecast_horizon_months": 12,
    "n_clusters": 20,
}


# ---------------------------------------------------------------------------
# Data loading + preparation
# ---------------------------------------------------------------------------

def load_training_data(data_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load cashflow time-series and profile data."""
    path = pathlib.Path(data_dir)

    cashflow_files = list(path.glob("cashflow*.csv")) + list(path.glob("cashflow*.parquet"))
    profile_files = list(path.glob("profile*.csv")) + list(path.glob("profile*.parquet"))

    def _load(files: list[pathlib.Path]) -> pd.DataFrame:
        parquets = [f for f in files if f.suffix == ".parquet"]
        csvs = [f for f in files if f.suffix == ".csv"]
        if parquets:
            return pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
        if csvs:
            return pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)
        return pd.DataFrame()

    cashflows = _load(cashflow_files)
    profiles = _load(profile_files)

    if cashflows.empty:
        raise FileNotFoundError(f"No cashflow data in {data_dir}")

    logger.info("Loaded %d cashflow rows, %d profiles", len(cashflows), len(profiles))
    return cashflows, profiles


def prepare_cluster_data(
    cashflows: pd.DataFrame,
    profiles: pd.DataFrame,
    n_clusters: int,
) -> dict[int, pd.DataFrame]:
    """Cluster farmers and return per-cluster Prophet-ready DataFrames."""
    from data.feature_engineering.cashflow_features import (
        compute_cluster_profiles,
        prepare_prophet_dataframe,
    )

    if profiles.empty:
        # No profile data → single global cluster
        prophet_df = prepare_prophet_dataframe(cashflows)
        return {0: prophet_df}

    cluster_map = compute_cluster_profiles(profiles, cashflows, n_clusters=n_clusters)

    # Merge cluster_id onto cashflows
    merged = cashflows.merge(cluster_map[["profile_id", "cluster_id"]], on="profile_id", how="left")
    merged["cluster_id"] = merged["cluster_id"].fillna(0).astype(int)

    cluster_data: dict[int, pd.DataFrame] = {}
    for cid in merged["cluster_id"].unique():
        subset = merged[merged["cluster_id"] == cid].copy()
        if len(subset) < 24:
            continue
        prophet_df = prepare_prophet_dataframe(subset)
        if len(prophet_df) >= 12:
            cluster_data[cid] = prophet_df

    logger.info("Prepared %d clusters for training", len(cluster_data))
    return cluster_data


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_prophet_model(
    df: pd.DataFrame,
    params: dict[str, Any],
) -> Any:
    """Train a single Prophet model on a cluster's time-series."""
    from prophet import Prophet

    regressor_cols = [
        "is_kharif", "is_rabi", "is_zaid",
        "weather_index", "msp_deviation", "diesel_price_index",
    ]

    model = Prophet(
        changepoint_prior_scale=float(params.get("changepoint_prior_scale", 0.1)),
        seasonality_prior_scale=float(params.get("seasonality_prior_scale", 10.0)),
        holidays_prior_scale=float(params.get("holidays_prior_scale", 10.0)),
        changepoint_range=float(params.get("changepoint_range", 0.85)),
        n_changepoints=int(params.get("n_changepoints", 25)),
        yearly_seasonality=params.get("yearly_seasonality", True),
        weekly_seasonality=params.get("weekly_seasonality", False),
        daily_seasonality=params.get("daily_seasonality", False),
    )

    # Add external regressors
    for col in regressor_cols:
        if col in df.columns:
            model.add_regressor(col)

    # Fit model (Prophet 1.3+ does not accept suppress_logging kwarg)
    import logging as _logging
    _prophet_logger = _logging.getLogger("prophet")
    _prev_level = _prophet_logger.level
    _prophet_logger.setLevel(_logging.WARNING)
    try:
        model.fit(df)
    finally:
        _prophet_logger.setLevel(_prev_level)

    return model


def train_all_clusters(
    cluster_data: dict[int, pd.DataFrame],
    params: dict[str, Any],
) -> dict[int, Any]:
    """Train one Prophet model per cluster."""
    models: dict[int, Any] = {}
    for cid, df in cluster_data.items():
        logger.info("Training cluster %d (%d rows) …", cid, len(df))
        try:
            model = train_prophet_model(df, params)
            models[cid] = model
        except Exception:
            logger.exception("Failed to train cluster %d", cid)
    return models


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_backtest(
    model: Any,
    df: pd.DataFrame,
    horizon_months: int = 6,
) -> dict[str, float]:
    """Walk-forward evaluation on the last `horizon_months`."""
    if len(df) < horizon_months + 12:
        return {"mape": float("nan"), "rmse": float("nan")}

    train_df = df.iloc[:-horizon_months]
    test_df = df.iloc[-horizon_months:]

    from prophet import Prophet

    regressor_cols = ["is_kharif", "is_rabi", "is_zaid", "weather_index", "msp_deviation", "diesel_price_index"]
    available_regs = [c for c in regressor_cols if c in df.columns]

    future = test_df[["ds"] + available_regs].copy()
    forecast = model.predict(future)

    y_true = test_df["y"].values
    y_pred = forecast["yhat"].values

    mape = np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), 1))) * 100
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

    return {"mape": round(float(mape), 2), "rmse": round(float(rmse), 2)}


# ---------------------------------------------------------------------------
# Save artefacts
# ---------------------------------------------------------------------------

def save_models(
    models: dict[int, Any],
    model_dir: str,
    params: dict[str, Any],
    metrics: dict[int, dict] | None = None,
) -> None:
    """Persist all cluster models as pickled Prophet objects."""
    out = pathlib.Path(model_dir)
    out.mkdir(parents=True, exist_ok=True)

    for cid, model in models.items():
        with open(out / f"prophet_cluster_{cid}.pkl", "wb") as f:
            pickle.dump(model, f)

    meta = {
        "model_type": "prophet_cluster",
        "num_clusters": len(models),
        "cluster_ids": [int(k) for k in models.keys()],
        "hyperparameters": params,
        "metrics": {str(k): v for k, v in (metrics or {}).items()},
    }
    with open(out / "model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    logger.info("Saved %d cluster models to %s", len(models), out)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train Prophet cash-flow models")
    parser.add_argument("--data-dir", default=INPUT_DIR)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--n-clusters", type=int, default=DEFAULT_HYPERPARAMS["n_clusters"])
    parser.add_argument("--changepoint-prior-scale", type=float, default=DEFAULT_HYPERPARAMS["changepoint_prior_scale"])
    parser.add_argument("--seasonality-prior-scale", type=float, default=DEFAULT_HYPERPARAMS["seasonality_prior_scale"])
    parser.add_argument("--forecast-horizon", type=int, default=DEFAULT_HYPERPARAMS["forecast_horizon_months"])
    args = parser.parse_args()

    params = DEFAULT_HYPERPARAMS.copy()
    params["n_clusters"] = args.n_clusters
    params["changepoint_prior_scale"] = args.changepoint_prior_scale
    params["seasonality_prior_scale"] = args.seasonality_prior_scale
    params["forecast_horizon_months"] = args.forecast_horizon

    logger.info("Loading data from %s …", args.data_dir)
    cashflows, profiles = load_training_data(args.data_dir)

    logger.info("Preparing cluster data …")
    cluster_data = prepare_cluster_data(cashflows, profiles, params["n_clusters"])

    logger.info("Training Prophet models …")
    models = train_all_clusters(cluster_data, params)

    # Evaluate each cluster
    metrics: dict[int, dict] = {}
    for cid, model in models.items():
        if cid in cluster_data:
            metrics[cid] = evaluate_backtest(model, cluster_data[cid], params["forecast_horizon_months"])
            logger.info("Cluster %d – MAPE: %.2f%%, RMSE: %.2f", cid, metrics[cid]["mape"], metrics[cid]["rmse"])

    save_models(models, args.model_dir, params, metrics)
    logger.info("Training complete ✓")


if __name__ == "__main__":
    main()
