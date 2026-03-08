"""Risk model evaluation script.

Computes classification + regression metrics against the test set.
Quality gates: F1 ≥ 0.78, AUC ≥ 0.85, MAE ≤ 80.

Used both locally and as a SageMaker Processing step.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CATEGORY_LABELS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]

# Quality gates
QUALITY_GATES = {
    "f1_weighted_min": 0.78,
    "auc_ovr_min": 0.85,
    "mae_max": 80,
}


def compute_risk_metrics(
    y_true_class: np.ndarray,
    y_pred_class: np.ndarray,
    y_true_scores: np.ndarray,
    y_pred_scores: np.ndarray,
    class_probs: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute classification + regression metrics from raw arrays.

    Pure function — no I/O. Used by ``evaluate_risk_model`` and tests.
    """
    f1_weighted = f1_score(y_true_class, y_pred_class, average="weighted")
    f1_macro = f1_score(y_true_class, y_pred_class, average="macro")
    acc = accuracy_score(y_true_class, y_pred_class)

    auc_ovr = 0.0
    if class_probs is not None:
        try:
            auc_ovr = roc_auc_score(
                y_true_class, class_probs, multi_class="ovr", average="weighted",
            )
        except ValueError:
            pass

    mae = mean_absolute_error(y_true_scores, y_pred_scores)
    rmse = float(np.sqrt(mean_squared_error(y_true_scores, y_pred_scores)))

    passed = (
        f1_weighted >= QUALITY_GATES["f1_weighted_min"]
        and auc_ovr >= QUALITY_GATES["auc_ovr_min"]
        and mae <= QUALITY_GATES["mae_max"]
    )

    return {
        "f1_weighted": round(float(f1_weighted), 4),
        "f1_macro": round(float(f1_macro), 4),
        "accuracy": round(float(acc), 4),
        "auc_ovr": round(float(auc_ovr), 4),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "passed": passed,
    }


def evaluate_risk_model(
    model_dir: str,
    test_dir: str,
    output_dir: str,
) -> dict[str, Any]:
    """Run full evaluation and write evaluation.json."""
    from data.feature_engineering.risk_features import (
        RISK_FEATURE_NAMES,
        RISK_TARGET_CLASSIFICATION,
        RISK_TARGET_REGRESSION,
        CATEGORY_ENCODING,
        extract_risk_features_batch,
    )

    # Load model
    classifier = xgb.Booster()
    classifier.load_model(str(pathlib.Path(model_dir) / "risk_classifier.xgb"))
    regressor = xgb.Booster()
    regressor.load_model(str(pathlib.Path(model_dir) / "risk_regressor.xgb"))

    # Load test data
    test_path = pathlib.Path(test_dir)
    parquets = list(test_path.glob("*.parquet"))
    csvs = list(test_path.glob("*.csv"))
    if parquets:
        df = pd.concat([pd.read_parquet(p) for p in parquets], ignore_index=True)
    else:
        df = pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)

    features = extract_risk_features_batch(df)
    score_labels = df[RISK_TARGET_REGRESSION].clip(0, 1000).values
    cat_labels = df[RISK_TARGET_CLASSIFICATION].map(CATEGORY_ENCODING).astype(int).values

    dmatrix = xgb.DMatrix(features, feature_names=list(features.columns))

    # Classification metrics
    class_probs = classifier.predict(dmatrix)
    if class_probs.ndim == 1:
        class_probs = class_probs.reshape(-1, 4)
    y_pred_class = np.argmax(class_probs, axis=1)

    f1_weighted = f1_score(cat_labels, y_pred_class, average="weighted")
    f1_macro = f1_score(cat_labels, y_pred_class, average="macro")
    accuracy = accuracy_score(cat_labels, y_pred_class)

    # AUC (one-vs-rest)
    try:
        auc_ovr = roc_auc_score(cat_labels, class_probs, multi_class="ovr", average="weighted")
    except ValueError:
        auc_ovr = 0.0

    cm = confusion_matrix(cat_labels, y_pred_class).tolist()

    # Regression metrics
    score_preds = regressor.predict(dmatrix)
    mae = mean_absolute_error(score_labels, score_preds)
    rmse = np.sqrt(mean_squared_error(score_labels, score_preds))

    # Per-class metrics
    report = classification_report(cat_labels, y_pred_class, target_names=CATEGORY_LABELS, output_dict=True)

    # Quality gate check
    gates_passed = (
        f1_weighted >= QUALITY_GATES["f1_weighted_min"]
        and auc_ovr >= QUALITY_GATES["auc_ovr_min"]
        and mae <= QUALITY_GATES["mae_max"]
    )

    evaluation = {
        "classification_metrics": {
            "f1_weighted": round(f1_weighted, 4),
            "f1_macro": round(f1_macro, 4),
            "accuracy": round(accuracy, 4),
            "auc_ovr": round(auc_ovr, 4),
            "confusion_matrix": cm,
            "per_class": report,
        },
        "regression_metrics": {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
        },
        "quality_gates": {
            "thresholds": QUALITY_GATES,
            "all_passed": gates_passed,
            "details": {
                "f1_weighted": {"value": round(f1_weighted, 4), "passed": f1_weighted >= QUALITY_GATES["f1_weighted_min"]},
                "auc_ovr": {"value": round(auc_ovr, 4), "passed": auc_ovr >= QUALITY_GATES["auc_ovr_min"]},
                "mae": {"value": round(mae, 2), "passed": mae <= QUALITY_GATES["mae_max"]},
            },
        },
        "dataset_size": len(df),
    }

    # Save evaluation
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2, default=str)

    logger.info("Risk model evaluation: F1=%.4f, AUC=%.4f, MAE=%.2f, Gates=%s",
                f1_weighted, auc_ovr, mae, "PASSED" if gates_passed else "FAILED")

    return evaluation


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="/opt/ml/processing/model")
    parser.add_argument("--test-dir", default="/opt/ml/processing/test")
    parser.add_argument("--output-dir", default="/opt/ml/processing/evaluation")
    args = parser.parse_args()
    evaluate_risk_model(args.model_dir, args.test_dir, args.output_dir)
