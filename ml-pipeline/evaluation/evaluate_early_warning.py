"""Early warning model evaluation.

Evaluates both Isolation Forest (anomaly detection) and LightGBM (severity).
Quality gates: F1 ≥ 0.70, Average Precision ≥ 0.60.
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
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SEVERITY_LABELS = ["INFO", "WARNING", "CRITICAL"]

QUALITY_GATES = {
    "f1_weighted_min": 0.70,
    "average_precision_min": 0.60,
}


def compute_early_warning_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    anomaly_scores: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute F1 + AP from raw arrays. No I/O."""
    f1_w = f1_score(y_true, y_pred, average="weighted")
    f1_m = f1_score(y_true, y_pred, average="macro")

    ap_val = 0.0
    if anomaly_scores is not None:
        binary = (np.asarray(y_true) >= 1).astype(int)
        try:
            ap_val = float(average_precision_score(binary, anomaly_scores))
        except ValueError:
            pass

    passed = (
        f1_w >= QUALITY_GATES["f1_weighted_min"]
        and (ap_val >= QUALITY_GATES["average_precision_min"] or anomaly_scores is None)
    )

    return {
        "f1_weighted": round(float(f1_w), 4),
        "f1_macro": round(float(f1_m), 4),
        "average_precision": round(float(ap_val), 4),
        "passed": passed,
    }


def evaluate_early_warning_model(
    model_dir: str,
    test_dir: str,
    output_dir: str,
) -> dict[str, Any]:
    """Evaluate IF + LightGBM early-warning models."""
    from data.feature_engineering.early_warning_features import (
        EARLY_WARNING_FEATURE_NAMES,
        extract_early_warning_features_batch,
        extract_severity_labels,
        SEVERITY_ENCODING,
    )

    model_path = pathlib.Path(model_dir)
    test_path = pathlib.Path(test_dir)

    # Load test data
    csvs = list(test_path.glob("*.csv"))
    parquets = list(test_path.glob("*.parquet"))
    if parquets:
        df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    else:
        df = pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)

    features = extract_early_warning_features_batch(df)
    labels = extract_severity_labels(df) if "severity" in df.columns else None

    metrics: dict[str, Any] = {"dataset_size": len(df)}

    # Evaluate Isolation Forest
    if_path = model_path / "isolation_forest.pkl"
    scaler_path = model_path / "scaler.pkl"
    anomaly_scores = None

    if if_path.exists() and scaler_path.exists():
        with open(if_path, "rb") as f:
            if_model = pickle.load(f)
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)

        X_scaled = scaler.transform(features)
        predictions = if_model.predict(X_scaled)
        raw_scores = if_model.decision_function(X_scaled)

        min_s, max_s = raw_scores.min(), raw_scores.max()
        if max_s - min_s > 0:
            anomaly_scores = 1.0 - (raw_scores - min_s) / (max_s - min_s)
        else:
            anomaly_scores = np.zeros_like(raw_scores)

        n_anomalies = int((predictions == -1).sum())
        metrics["isolation_forest"] = {
            "anomaly_rate": round(n_anomalies / len(df), 4),
            "n_anomalies": n_anomalies,
            "mean_score": round(float(np.mean(anomaly_scores)), 4),
        }

        if labels is not None:
            binary = (labels >= 1).astype(int)
            ap = average_precision_score(binary, anomaly_scores)
            metrics["isolation_forest"]["average_precision"] = round(float(ap), 4)

    # Evaluate LightGBM
    lgb_path = model_path / "lightgbm_severity.pkl"
    if lgb_path.exists() and labels is not None:
        with open(lgb_path, "rb") as f:
            lgb_model = pickle.load(f)

        features_with_scores = features.copy()
        features_with_scores["anomaly_score"] = anomaly_scores if anomaly_scores is not None else 0.5

        y_pred = lgb_model.predict(features_with_scores)
        y_proba = lgb_model.predict_proba(features_with_scores)

        f1_weighted = f1_score(labels, y_pred, average="weighted")
        f1_macro = f1_score(labels, y_pred, average="macro")
        cm = confusion_matrix(labels, y_pred).tolist()
        report = classification_report(labels, y_pred, target_names=SEVERITY_LABELS, output_dict=True)

        metrics["lightgbm"] = {
            "f1_weighted": round(float(f1_weighted), 4),
            "f1_macro": round(float(f1_macro), 4),
            "confusion_matrix": cm,
            "per_class": report,
        }

        # For Pipeline quality gate
        metrics["classification_metrics"] = {
            "f1_weighted": round(float(f1_weighted), 4),
        }

    # Quality gates
    f1_val = metrics.get("lightgbm", {}).get("f1_weighted", 0)
    ap_val = metrics.get("isolation_forest", {}).get("average_precision", 0)

    gates_passed = (
        f1_val >= QUALITY_GATES["f1_weighted_min"]
        and ap_val >= QUALITY_GATES["average_precision_min"]
    )

    metrics["quality_gates"] = {
        "thresholds": QUALITY_GATES,
        "all_passed": gates_passed,
    }

    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "evaluation.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    logger.info("Early warning evaluation: IF_AP=%.4f, LGB_F1=%.4f, Gates=%s",
                ap_val, f1_val, "PASSED" if gates_passed else "FAILED")
    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="/opt/ml/processing/model")
    parser.add_argument("--test-dir", default="/opt/ml/processing/test")
    parser.add_argument("--output-dir", default="/opt/ml/processing/evaluation")
    args = parser.parse_args()
    evaluate_early_warning_model(args.model_dir, args.test_dir, args.output_dir)
