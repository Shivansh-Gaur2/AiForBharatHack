"""Backtesting framework for time-series models.

Walk-forward validation with expanding window for Prophet and
early-warning models. Simulates real-world deployment drift.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def walk_forward_backtest(
    data: pd.DataFrame,
    train_fn: callable,
    predict_fn: callable,
    initial_train_months: int = 24,
    step_months: int = 1,
    forecast_horizon: int = 3,
) -> dict[str, Any]:
    """Walk-forward backtesting for time-series forecasting models.

    Expands the training window by `step_months` at each step,
    retrains the model, and evaluates on the next `forecast_horizon` months.
    """
    data = data.sort_values("ds").reset_index(drop=True)
    unique_months = data.groupby(data["ds"].dt.to_period("M")).first().index.sort_values()

    if len(unique_months) < initial_train_months + forecast_horizon:
        logger.warning("Not enough data for backtesting")
        return {"error": "insufficient_data"}

    results: list[dict[str, Any]] = []
    step = initial_train_months

    while step + forecast_horizon <= len(unique_months):
        train_end = unique_months[step - 1]
        test_start = unique_months[step]
        test_end = unique_months[min(step + forecast_horizon - 1, len(unique_months) - 1)]

        train_mask = data["ds"].dt.to_period("M") <= train_end
        test_mask = (data["ds"].dt.to_period("M") >= test_start) & (data["ds"].dt.to_period("M") <= test_end)

        train_df = data[train_mask].copy()
        test_df = data[test_mask].copy()

        if len(test_df) == 0:
            break

        try:
            model = train_fn(train_df)
            predictions = predict_fn(model, test_df)

            y_true = test_df["y"].values
            y_pred = predictions

            mape = np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), 1))) * 100
            rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

            results.append({
                "train_end": str(train_end),
                "test_start": str(test_start),
                "test_end": str(test_end),
                "n_train": len(train_df),
                "n_test": len(test_df),
                "mape": round(float(mape), 2),
                "rmse": round(float(rmse), 2),
            })
        except Exception:
            logger.exception("Backtest step failed at %s", test_start)

        step += step_months

    # Aggregate
    if results:
        mapes = [r["mape"] for r in results]
        rmses = [r["rmse"] for r in results]
        summary = {
            "n_steps": len(results),
            "mean_mape": round(float(np.mean(mapes)), 2),
            "std_mape": round(float(np.std(mapes)), 2),
            "mean_rmse": round(float(np.mean(rmses)), 2),
            "std_rmse": round(float(np.std(rmses)), 2),
            "max_mape": round(float(max(mapes)), 2),
            "min_mape": round(float(min(mapes)), 2),
        }
    else:
        summary = {"n_steps": 0}

    return {"summary": summary, "steps": results}


def backtest_early_warning(
    events: pd.DataFrame,
    train_fn: callable,
    predict_fn: callable,
    initial_train_fraction: float = 0.7,
) -> dict[str, Any]:
    """Time-ordered backtesting for early-warning anomaly detection.

    Uses temporal split (no future leak) to evaluate alert precision.
    """
    events = events.sort_values(["year", "month"]).reset_index(drop=True)
    split_idx = int(len(events) * initial_train_fraction)

    train_df = events.iloc[:split_idx]
    test_df = events.iloc[split_idx:]

    model = train_fn(train_df)
    predictions = predict_fn(model, test_df)

    if "severity" in test_df.columns:
        from sklearn.metrics import f1_score, classification_report

        from data.feature_engineering.early_warning_features import SEVERITY_ENCODING

        y_true = test_df["severity"].map(SEVERITY_ENCODING).astype(int).values
        f1 = f1_score(y_true, predictions, average="weighted")
        report = classification_report(y_true, predictions, output_dict=True)

        return {
            "n_train": len(train_df),
            "n_test": len(test_df),
            "f1_weighted": round(float(f1), 4),
            "classification_report": report,
        }

    return {
        "n_train": len(train_df),
        "n_test": len(test_df),
        "predictions_shape": len(predictions),
    }


def save_backtest_results(
    results: dict[str, Any],
    output_path: str | pathlib.Path,
    filename: str = "backtest_results.json",
) -> None:
    """Persist backtest results."""
    out = pathlib.Path(output_path)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Backtest results saved to %s", out / filename)
