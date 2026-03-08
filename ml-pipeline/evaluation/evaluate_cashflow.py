"""Cash flow model evaluation.

Quality gate: MAPE ≤ 15% across clusters, RMSE reasonable.
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
logging.basicConfig(level=logging.INFO)

QUALITY_GATES = {
    "mape_max": 15.0,
    "rmse_max": 20_000,
}


def compute_cashflow_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Compute MAPE + RMSE from raw arrays. No I/O."""
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    mape = float(np.mean(np.abs((y_true_arr - y_pred_arr) / np.maximum(np.abs(y_true_arr), 1))) * 100)
    rmse = float(np.sqrt(np.mean((y_true_arr - y_pred_arr) ** 2)))

    passed = mape <= QUALITY_GATES["mape_max"] and rmse <= QUALITY_GATES["rmse_max"]
    return {
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "passed": passed,
    }


def evaluate_cashflow_model(
    model_dir: str,
    test_dir: str,
    output_dir: str,
) -> dict[str, Any]:
    """Evaluate Prophet cluster models on held-out test data."""
    from data.feature_engineering.cashflow_features import prepare_prophet_dataframe

    model_path = pathlib.Path(model_dir)
    test_path = pathlib.Path(test_dir)

    # Load test data
    csvs = list(test_path.glob("*.csv"))
    parquets = list(test_path.glob("*.parquet"))
    if parquets:
        test_df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    else:
        test_df = pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)

    # Load models
    models: dict[int, Any] = {}
    for pkl in model_path.glob("prophet_cluster_*.pkl"):
        cid = int(pkl.stem.split("_")[-1])
        with open(pkl, "rb") as f:
            models[cid] = pickle.load(f)

    if not models:
        logger.warning("No Prophet models found in %s", model_dir)
        return {"error": "no_models_found"}

    # Evaluate per cluster
    cluster_metrics: dict[str, dict] = {}
    all_y_true = []
    all_y_pred = []

    for cid, model in models.items():
        prophet_df = prepare_prophet_dataframe(test_df)
        if len(prophet_df) < 3:
            continue

        # Predict
        regressor_cols = ["is_kharif", "is_rabi", "is_zaid", "weather_index", "msp_deviation", "diesel_price_index"]
        available_regs = [c for c in regressor_cols if c in prophet_df.columns and c in model.extra_regressors]
        future = prophet_df[["ds"] + available_regs].copy()

        try:
            forecast = model.predict(future)
        except Exception:
            logger.exception("Prediction failed for cluster %d", cid)
            continue

        y_true = prophet_df["y"].values
        y_pred = forecast["yhat"].values

        mape = np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), 1))) * 100
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

        cluster_metrics[str(cid)] = {
            "mape": round(float(mape), 2),
            "rmse": round(float(rmse), 2),
            "n_samples": len(y_true),
        }

        all_y_true.extend(y_true.tolist())
        all_y_pred.extend(y_pred.tolist())

    # Aggregate metrics
    if all_y_true:
        y_true_arr = np.array(all_y_true)
        y_pred_arr = np.array(all_y_pred)
        overall_mape = np.mean(np.abs((y_true_arr - y_pred_arr) / np.maximum(np.abs(y_true_arr), 1))) * 100
        overall_rmse = np.sqrt(np.mean((y_true_arr - y_pred_arr) ** 2))
    else:
        overall_mape = float("inf")
        overall_rmse = float("inf")

    gates_passed = (
        overall_mape <= QUALITY_GATES["mape_max"]
        and overall_rmse <= QUALITY_GATES["rmse_max"]
    )

    evaluation = {
        "regression_metrics": {
            "mape": round(overall_mape, 2),
            "rmse": round(overall_rmse, 2),
        },
        "per_cluster": cluster_metrics,
        "quality_gates": {
            "thresholds": QUALITY_GATES,
            "all_passed": gates_passed,
        },
        "num_clusters_evaluated": len(cluster_metrics),
        "total_samples": len(all_y_true),
    }

    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2, default=str)

    logger.info("Cashflow evaluation: MAPE=%.2f%%, RMSE=%.2f, Gates=%s",
                overall_mape, overall_rmse, "PASSED" if gates_passed else "FAILED")
    return evaluation


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="/opt/ml/processing/model")
    parser.add_argument("--test-dir", default="/opt/ml/processing/test")
    parser.add_argument("--output-dir", default="/opt/ml/processing/evaluation")
    args = parser.parse_args()
    evaluate_cashflow_model(args.model_dir, args.test_dir, args.output_dir)
