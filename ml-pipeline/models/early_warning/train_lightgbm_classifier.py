"""LightGBM severity classifier – Phase B of the early-warning model.

Takes the anomaly_score from Isolation Forest as an additional feature
and classifies alerts into INFO / WARNING / CRITICAL.
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
import lightgbm as lgb
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import classification_report, f1_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
INPUT_DIR = os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "objective": "multiclass",
    "num_class": 3,
    "metric": "multi_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "max_depth": -1,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "n_estimators": 500,
    "early_stopping_rounds": 30,
    "class_weight": "balanced",
}

SEVERITY_LABELS = ["INFO", "WARNING", "CRITICAL"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_and_prepare(
    data_dir: str,
    anomaly_scores: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Load early-warning data and add anomaly scores as a feature."""
    from models.early_warning.train_isolation_forest import load_training_data
    from data.feature_engineering.early_warning_features import (
        extract_early_warning_features_batch,
        extract_severity_labels,
    )

    df = load_training_data(data_dir)
    features = extract_early_warning_features_batch(df)
    labels = extract_severity_labels(df)

    # Add anomaly score from Phase A as an extra feature
    if anomaly_scores is not None and len(anomaly_scores) == len(features):
        features["anomaly_score"] = anomaly_scores
    else:
        features["anomaly_score"] = 0.5  # Default if IF not available

    return features, labels


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_lightgbm_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict[str, Any],
) -> lgb.LGBMClassifier:
    """Train LightGBM multi-class severity classifier."""
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42,
    )

    model = lgb.LGBMClassifier(
        objective=params.get("objective", "multiclass"),
        num_class=params.get("num_class", 3),
        boosting_type=params.get("boosting_type", "gbdt"),
        num_leaves=int(params.get("num_leaves", 31)),
        learning_rate=float(params.get("learning_rate", 0.05)),
        max_depth=int(params.get("max_depth", -1)),
        min_child_samples=int(params.get("min_child_samples", 20)),
        subsample=float(params.get("subsample", 0.8)),
        colsample_bytree=float(params.get("colsample_bytree", 0.8)),
        reg_alpha=float(params.get("reg_alpha", 0.1)),
        reg_lambda=float(params.get("reg_lambda", 1.0)),
        n_estimators=int(params.get("n_estimators", 500)),
        class_weight=params.get("class_weight", "balanced"),
        random_state=42,
        verbose=-1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(int(params.get("early_stopping_rounds", 30)))],
    )

    y_pred = model.predict(X_val)
    f1 = f1_score(y_val, y_pred, average="weighted")
    logger.info("LightGBM F1 (weighted): %.4f", f1)
    logger.info("\n%s", classification_report(y_val, y_pred, target_names=SEVERITY_LABELS))

    return model


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict[str, Any],
    n_folds: int = 5,
) -> dict[str, float]:
    """Stratified k-fold cross-validation."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    scores = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = lgb.LGBMClassifier(
            n_estimators=int(params.get("n_estimators", 500)),
            num_leaves=int(params.get("num_leaves", 31)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            class_weight=params.get("class_weight", "balanced"),
            verbose=-1,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)
        f1 = f1_score(y_val, y_pred, average="weighted")
        scores.append(f1)
        logger.info("Fold %d F1: %.4f", fold + 1, f1)

    return {
        "mean_f1": round(float(np.mean(scores)), 4),
        "std_f1": round(float(np.std(scores)), 4),
    }


# ---------------------------------------------------------------------------
# Save artefacts
# ---------------------------------------------------------------------------

def save_model(
    model: lgb.LGBMClassifier,
    model_dir: str,
    params: dict[str, Any],
    metrics: dict[str, float] | None = None,
) -> None:
    out = pathlib.Path(model_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "lightgbm_severity.pkl", "wb") as f:
        pickle.dump(model, f)

    # Also save in LightGBM native format
    model.booster_.save_model(str(out / "lightgbm_severity.txt"))

    # Feature importance
    importance = dict(zip(model.feature_name_, model.feature_importances_.tolist()))

    meta = {
        "model_type": "lightgbm_severity_classifier",
        "feature_names": model.feature_name_,
        "num_features": len(model.feature_name_),
        "hyperparameters": params,
        "metrics": metrics or {},
        "feature_importance": importance,
    }
    with open(out / "model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    logger.info("Model saved to %s", out)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train LightGBM severity classifier")
    parser.add_argument("--data-dir", default=INPUT_DIR)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--if-model-dir", default=None, help="Path to pre-trained IF model for anomaly scores")
    parser.add_argument("--n-estimators", type=int, default=DEFAULT_HYPERPARAMS["n_estimators"])
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_HYPERPARAMS["learning_rate"])
    args = parser.parse_args()

    params = DEFAULT_HYPERPARAMS.copy()
    params["n_estimators"] = args.n_estimators
    params["learning_rate"] = args.learning_rate

    # Load IF scores if available
    anomaly_scores = None
    if args.if_model_dir:
        if_path = pathlib.Path(args.if_model_dir)
        if (if_path / "isolation_forest.pkl").exists():
            from models.early_warning.train_isolation_forest import (
                compute_anomaly_scores,
                load_training_data,
            )
            from data.feature_engineering.early_warning_features import (
                extract_early_warning_features_batch,
            )

            with open(if_path / "isolation_forest.pkl", "rb") as f:
                if_model = pickle.load(f)
            with open(if_path / "scaler.pkl", "rb") as f:
                if_scaler = pickle.load(f)

            raw_df = load_training_data(args.data_dir)
            if_features = extract_early_warning_features_batch(raw_df)
            anomaly_scores = compute_anomaly_scores(if_model, if_scaler, if_features)
            logger.info("Loaded anomaly scores from IF model")

    features, labels = load_and_prepare(args.data_dir, anomaly_scores)

    logger.info("Cross-validating …")
    cv_metrics = cross_validate(features, labels, params)
    logger.info("CV results: %s", cv_metrics)

    logger.info("Training final model …")
    model = train_lightgbm_classifier(features, labels, params)

    save_model(model, args.model_dir, params, {**cv_metrics})
    logger.info("Training complete ✓")


if __name__ == "__main__":
    main()
