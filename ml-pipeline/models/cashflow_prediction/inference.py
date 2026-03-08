"""Prophet cash-flow model – SageMaker inference handler.

Returns per-month income predictions with uncertainty bands.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import pickle
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def model_fn(model_dir: str) -> dict[str, Any]:
    """Load cluster Prophet models from the model directory."""
    path = pathlib.Path(model_dir)

    models: dict[int, Any] = {}
    for pkl in sorted(path.glob("prophet_cluster_*.pkl")):
        cid = int(pkl.stem.split("_")[-1])
        with open(pkl, "rb") as f:
            models[cid] = pickle.load(f)

    meta_path = path / "model_metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    logger.info("Loaded %d cluster models", len(models))
    return {"models": models, "metadata": metadata}


def input_fn(request_body: str, content_type: str = "application/json") -> dict[str, Any]:
    """Deserialise forecast request."""
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")

    payload = json.loads(request_body)
    return payload


def predict_fn(payload: dict[str, Any], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate cash-flow forecasts.

    Payload should contain:
    - cluster_id (int, default 0)
    - horizon_months (int, default 12)
    - regressors (optional dict of future regressor values per month)
    """
    models = model["models"]
    cluster_id = int(payload.get("cluster_id", 0))
    horizon = int(payload.get("horizon_months", 12))

    if cluster_id not in models:
        # Fall back to cluster 0 (global) or first available
        cluster_id = 0 if 0 in models else next(iter(models.keys()))

    prophet_model = models[cluster_id]

    # Build future DataFrame
    future = prophet_model.make_future_dataframe(periods=horizon, freq="MS")

    # Add regressors
    regressor_cols = ["is_kharif", "is_rabi", "is_zaid", "weather_index", "msp_deviation", "diesel_price_index"]
    regressors = payload.get("regressors", {})

    for col in regressor_cols:
        if col in prophet_model.extra_regressors:
            if col in regressors:
                values = regressors[col]
                # Extend to match future length
                while len(values) < len(future):
                    values.append(values[-1] if values else 0.0)
                future[col] = values[:len(future)]
            elif col.startswith("is_"):
                # Auto-fill season flags from month
                from data.feature_engineering.cashflow_features import _month_to_season_flags
                seasons = future["ds"].dt.month.apply(_month_to_season_flags)
                season_idx = {"is_kharif": 0, "is_rabi": 1, "is_zaid": 2}
                future[col] = seasons.apply(lambda x: x[season_idx.get(col, 0)])
            else:
                future[col] = 0.0

    forecast = prophet_model.predict(future)

    # Extract only the forecast period (last N months)
    forecast_period = forecast.tail(horizon)

    results = []
    for _, row in forecast_period.iterrows():
        results.append({
            "date": row["ds"].strftime("%Y-%m-%d"),
            "predicted_income": round(float(row["yhat"]), 2),
            "lower_bound": round(float(row["yhat_lower"]), 2),
            "upper_bound": round(float(row["yhat_upper"]), 2),
            "trend": round(float(row["trend"]), 2),
        })

    return results


def output_fn(prediction: list[dict], accept: str = "application/json") -> str:
    if accept == "application/json":
        return json.dumps(prediction, default=str)
    raise ValueError(f"Unsupported accept type: {accept}")
