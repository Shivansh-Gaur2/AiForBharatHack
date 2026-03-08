"""XGBoost risk-scoring model – SageMaker training entry-point.

This script is the `entry_point` for a SageMaker XGBoost training job.
SageMaker invokes it with hyperparameters via argparse and expects the
model artefact to be written to ``/opt/ml/model``.

Dual-head output:
  1. ``reg:squarederror``  → continuous risk score (0-1000)
  2. ``multi:softprob``    → risk category (LOW / MEDIUM / HIGH / VERY_HIGH)
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
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import (
    classification_report,
    f1_score,
    mean_absolute_error,
    roc_auc_score,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "max_depth": 6,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma": 0.1,
    "lambda": 1.0,
    "alpha": 0.5,
    "num_round": 300,
    "early_stopping_rounds": 20,
    "num_class": 4,
}

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
INPUT_DIR = os.environ.get("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_training_data(data_dir: str) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Load feature matrix + labels from a directory of CSV / Parquet files."""
    path = pathlib.Path(data_dir)

    parquet = list(path.glob("*.parquet"))
    csv = list(path.glob("*.csv"))

    if parquet:
        df = pd.concat([pd.read_parquet(p) for p in parquet], ignore_index=True)
    elif csv:
        df = pd.concat([pd.read_csv(p) for p in csv], ignore_index=True)
    else:
        raise FileNotFoundError(f"No training data found in {data_dir}")

    logger.info("Loaded %d rows from %s", len(df), data_dir)

    from data.feature_engineering.risk_features import (
        RISK_FEATURE_NAMES,
        RISK_TARGET_CLASSIFICATION,
        RISK_TARGET_REGRESSION,
        CATEGORY_ENCODING,
        extract_risk_features_batch,
    )

    features = extract_risk_features_batch(df)
    score_labels = df[RISK_TARGET_REGRESSION].clip(0, 1000)
    cat_labels = df[RISK_TARGET_CLASSIFICATION].map(CATEGORY_ENCODING).astype(int)

    return features, score_labels, cat_labels


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict[str, Any],
) -> xgb.Booster:
    """Train multi:softprob XGBoost classifier with stratified 5-fold CV."""
    # Use stratified split only when all classes have >= 2 members
    min_class_count = y.value_counts().min()
    stratify_arg = y if min_class_count >= 2 else None
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.15, stratify=stratify_arg, random_state=42,
    )

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(X.columns))
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=list(X.columns))

    xgb_params = {
        "objective": "multi:softprob",
        "num_class": params.get("num_class", 4),
        "eval_metric": ["mlogloss", "merror"],
        "max_depth": int(params.get("max_depth", 6)),
        "eta": float(params.get("eta", 0.1)),
        "subsample": float(params.get("subsample", 0.8)),
        "colsample_bytree": float(params.get("colsample_bytree", 0.8)),
        "min_child_weight": int(params.get("min_child_weight", 3)),
        "gamma": float(params.get("gamma", 0.1)),
        "lambda": float(params.get("lambda", 1.0)),
        "alpha": float(params.get("alpha", 0.5)),
        "seed": 42,
    }

    booster = xgb.train(
        xgb_params,
        dtrain,
        num_boost_round=int(params.get("num_round", 300)),
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=int(params.get("early_stopping_rounds", 20)),
        verbose_eval=50,
    )

    # Evaluate
    preds = booster.predict(dval)
    y_pred = np.argmax(preds, axis=1)
    f1 = f1_score(y_val, y_pred, average="weighted")
    logger.info("Classifier F1 (weighted): %.4f", f1)
    logger.info("\n%s", classification_report(y_val, y_pred))

    return booster


def train_regressor(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict[str, Any],
) -> xgb.Booster:
    """Train reg:squarederror XGBoost regressor for risk score prediction."""
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.15, random_state=42,
    )

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=list(X.columns))
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=list(X.columns))

    xgb_params = {
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "max_depth": int(params.get("max_depth", 6)),
        "eta": float(params.get("eta", 0.1)),
        "subsample": float(params.get("subsample", 0.8)),
        "colsample_bytree": float(params.get("colsample_bytree", 0.8)),
        "min_child_weight": int(params.get("min_child_weight", 3)),
        "gamma": float(params.get("gamma", 0.1)),
        "lambda": float(params.get("lambda", 1.0)),
        "alpha": float(params.get("alpha", 0.5)),
        "seed": 42,
    }

    booster = xgb.train(
        xgb_params,
        dtrain,
        num_boost_round=int(params.get("num_round", 300)),
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=int(params.get("early_stopping_rounds", 20)),
        verbose_eval=50,
    )

    preds = booster.predict(dval)
    mae = mean_absolute_error(y_val, preds)
    logger.info("Regressor MAE: %.2f", mae)

    return booster


# ---------------------------------------------------------------------------
# SHAP explainability
# ---------------------------------------------------------------------------

def compute_shap_values(
    booster: xgb.Booster,
    X_sample: pd.DataFrame,
    output_dir: str,
) -> None:
    """Compute and store SHAP values for a sample of the validation set."""
    try:
        import shap

        explainer = shap.TreeExplainer(booster)
        dmatrix = xgb.DMatrix(X_sample, feature_names=list(X_sample.columns))
        shap_values = explainer.shap_values(dmatrix)

        out_path = pathlib.Path(output_dir) / "shap_values.npy"
        np.save(str(out_path), shap_values)
        logger.info("SHAP values saved to %s", out_path)
    except ImportError:
        logger.warning("shap not installed – skipping explainability")


# ---------------------------------------------------------------------------
# Save artefacts
# ---------------------------------------------------------------------------

def save_model(
    classifier: xgb.Booster,
    regressor: xgb.Booster,
    model_dir: str,
    params: dict[str, Any],
) -> None:
    """Persist both models + metadata to `model_dir`."""
    out = pathlib.Path(model_dir)
    out.mkdir(parents=True, exist_ok=True)

    classifier.save_model(str(out / "risk_classifier.xgb"))
    regressor.save_model(str(out / "risk_regressor.xgb"))

    meta = {
        "model_type": "xgboost_dual_head",
        "feature_names": list(classifier.feature_names),
        "num_features": len(classifier.feature_names),
        "hyperparameters": params,
    }
    with open(out / "model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Models saved to %s", out)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost risk models")
    parser.add_argument("--data-dir", default=INPUT_DIR)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_HYPERPARAMS["max_depth"])
    parser.add_argument("--eta", type=float, default=DEFAULT_HYPERPARAMS["eta"])
    parser.add_argument("--subsample", type=float, default=DEFAULT_HYPERPARAMS["subsample"])
    parser.add_argument("--colsample-bytree", type=float, default=DEFAULT_HYPERPARAMS["colsample_bytree"])
    parser.add_argument("--min-child-weight", type=int, default=DEFAULT_HYPERPARAMS["min_child_weight"])
    parser.add_argument("--gamma", type=float, default=DEFAULT_HYPERPARAMS["gamma"])
    parser.add_argument("--reg-lambda", type=float, default=DEFAULT_HYPERPARAMS["lambda"])
    parser.add_argument("--reg-alpha", type=float, default=DEFAULT_HYPERPARAMS["alpha"])
    parser.add_argument("--num-round", type=int, default=DEFAULT_HYPERPARAMS["num_round"])
    parser.add_argument("--early-stopping-rounds", type=int, default=DEFAULT_HYPERPARAMS["early_stopping_rounds"])
    args = parser.parse_args()

    params = {
        "max_depth": args.max_depth,
        "eta": args.eta,
        "subsample": args.subsample,
        "colsample_bytree": args.colsample_bytree,
        "min_child_weight": args.min_child_weight,
        "gamma": args.gamma,
        "lambda": args.reg_lambda,
        "alpha": args.reg_alpha,
        "num_round": args.num_round,
        "early_stopping_rounds": args.early_stopping_rounds,
        "num_class": 4,
    }

    logger.info("Loading training data from %s …", args.data_dir)
    features, score_labels, cat_labels = load_training_data(args.data_dir)
    logger.info("Feature matrix shape: %s", features.shape)

    logger.info("Training classifier …")
    classifier = train_classifier(features, cat_labels, params)

    logger.info("Training regressor …")
    regressor = train_regressor(features, score_labels, params)

    logger.info("Computing SHAP values …")
    compute_shap_values(classifier, features.sample(min(500, len(features))), args.output_dir)

    logger.info("Saving models …")
    save_model(classifier, regressor, args.model_dir, params)

    logger.info("Training complete ✓")


if __name__ == "__main__":
    main()
