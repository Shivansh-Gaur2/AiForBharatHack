"""Isolation Forest anomaly detection – Phase A of the early-warning model.

Trains an unsupervised anomaly detector on the 22-feature early-warning
vector. Outputs an anomaly_score ∈ [0, 1] where higher = more anomalous.
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
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_recall_curve, average_precision_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
INPUT_DIR = os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_samples": "auto",
    "contamination": 0.08,
    "max_features": 1.0,
    "random_state": 42,
    "n_jobs": -1,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_training_data(data_dir: str) -> pd.DataFrame:
    """Load early-warning events data."""
    path = pathlib.Path(data_dir)
    parquets = list(path.glob("*.parquet"))
    csvs = list(path.glob("*.csv"))

    if parquets:
        df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    elif csvs:
        df = pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)
    else:
        raise FileNotFoundError(f"No training data in {data_dir}")

    logger.info("Loaded %d rows from %s", len(df), data_dir)
    return df


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_isolation_forest(
    features: pd.DataFrame,
    params: dict[str, Any],
) -> tuple[IsolationForest, StandardScaler]:
    """Train Isolation Forest and return the model + fitted scaler."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    model = IsolationForest(
        n_estimators=int(params.get("n_estimators", 200)),
        max_samples=params.get("max_samples", "auto"),
        contamination=float(params.get("contamination", 0.08)),
        max_features=float(params.get("max_features", 1.0)),
        random_state=int(params.get("random_state", 42)),
        n_jobs=int(params.get("n_jobs", -1)),
    )

    model.fit(X_scaled)
    logger.info("Isolation Forest trained on %d samples", len(features))

    return model, scaler


def compute_anomaly_scores(
    model: IsolationForest,
    scaler: StandardScaler,
    features: pd.DataFrame,
) -> np.ndarray:
    """Return anomaly scores ∈ [0, 1] (higher = more anomalous)."""
    X_scaled = scaler.transform(features)
    # decision_function returns negative scores for anomalies
    raw_scores = model.decision_function(X_scaled)
    # Normalise to [0, 1] range where 1 = most anomalous
    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s - min_s > 0:
        normalised = 1.0 - (raw_scores - min_s) / (max_s - min_s)
    else:
        normalised = np.zeros_like(raw_scores)
    return normalised


def evaluate_if(
    model: IsolationForest,
    scaler: StandardScaler,
    features: pd.DataFrame,
    labels: pd.Series | None = None,
) -> dict[str, float]:
    """Evaluate anomaly detector performance."""
    scores = compute_anomaly_scores(model, scaler, features)
    predictions = model.predict(scaler.transform(features))
    n_anomalies = int((predictions == -1).sum())
    anomaly_rate = n_anomalies / len(features)

    metrics = {
        "anomaly_rate": round(anomaly_rate, 4),
        "n_anomalies": n_anomalies,
        "mean_anomaly_score": round(float(scores.mean()), 4),
        "std_anomaly_score": round(float(scores.std()), 4),
    }

    # If we have severity labels, compute AP against WARNING+CRITICAL
    if labels is not None:
        binary_labels = (labels >= 1).astype(int)  # WARNING or CRITICAL
        ap = average_precision_score(binary_labels, scores)
        metrics["average_precision"] = round(float(ap), 4)

    return metrics


# ---------------------------------------------------------------------------
# Save artefacts
# ---------------------------------------------------------------------------

def save_model(
    model: IsolationForest,
    scaler: StandardScaler,
    model_dir: str,
    params: dict[str, Any],
    metrics: dict[str, float] | None = None,
) -> None:
    out = pathlib.Path(model_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "isolation_forest.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(out / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_type": "isolation_forest",
        "hyperparameters": params,
        "metrics": metrics or {},
    }
    with open(out / "model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    logger.info("Model saved to %s", out)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train Isolation Forest anomaly detector")
    parser.add_argument("--data-dir", default=INPUT_DIR)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--n-estimators", type=int, default=DEFAULT_HYPERPARAMS["n_estimators"])
    parser.add_argument("--contamination", type=float, default=DEFAULT_HYPERPARAMS["contamination"])
    args = parser.parse_args()

    params = DEFAULT_HYPERPARAMS.copy()
    params["n_estimators"] = args.n_estimators
    params["contamination"] = args.contamination

    df = load_training_data(args.data_dir)

    from data.feature_engineering.early_warning_features import (
        EARLY_WARNING_FEATURE_NAMES,
        extract_early_warning_features_batch,
        extract_severity_labels,
    )

    features = extract_early_warning_features_batch(df)
    labels = extract_severity_labels(df) if "severity" in df.columns else None

    model, scaler = train_isolation_forest(features, params)
    metrics = evaluate_if(model, scaler, features, labels)
    logger.info("Metrics: %s", json.dumps(metrics, indent=2))

    save_model(model, scaler, args.model_dir, params, metrics)
    logger.info("Training complete ✓")


if __name__ == "__main__":
    main()
