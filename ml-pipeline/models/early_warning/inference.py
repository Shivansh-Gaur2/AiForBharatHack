"""Early warning model – SageMaker inference handler.

Runs the two-phase pipeline:
  Phase A: Isolation Forest → anomaly_score
  Phase B: LightGBM → severity classification (INFO/WARNING/CRITICAL)
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import pickle
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

SEVERITY_LABELS = ["INFO", "WARNING", "CRITICAL"]


def model_fn(model_dir: str) -> dict[str, Any]:
    """Load both IF and LightGBM models."""
    path = pathlib.Path(model_dir)

    models: dict[str, Any] = {}

    # Isolation Forest
    if_path = path / "isolation_forest.pkl"
    scaler_path = path / "scaler.pkl"
    if if_path.exists() and scaler_path.exists():
        with open(if_path, "rb") as f:
            models["isolation_forest"] = pickle.load(f)
        with open(scaler_path, "rb") as f:
            models["scaler"] = pickle.load(f)

    # LightGBM
    lgb_path = path / "lightgbm_severity.pkl"
    if lgb_path.exists():
        with open(lgb_path, "rb") as f:
            models["lightgbm"] = pickle.load(f)

    meta_path = path / "model_metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            models["metadata"] = json.load(f)

    logger.info("Loaded [IF=%s, LGB=%s]", "isolation_forest" in models, "lightgbm" in models)
    return models


def input_fn(request_body: str, content_type: str = "application/json") -> list[dict[str, Any]]:
    if content_type != "application/json":
        raise ValueError(f"Unsupported: {content_type}")
    payload = json.loads(request_body)
    return payload if isinstance(payload, list) else [payload]


def predict_fn(instances: list[dict], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Two-phase early-warning prediction."""
    from data.feature_engineering.early_warning_features import (
        EARLY_WARNING_FEATURE_NAMES,
        extract_early_warning_features,
    )

    # Phase A: Anomaly detection
    results = []
    if_model = model.get("isolation_forest")
    scaler = model.get("scaler")
    lgb_model = model.get("lightgbm")

    for inst in instances:
        # Extract 22 features
        features = extract_early_warning_features(
            profile=inst.get("profile", {}),
            cashflow_history=inst.get("cashflow_history", []),
            loan_data=inst.get("loan_data", {}),
            alert_history=inst.get("alert_history"),
        )

        feature_vec = np.array([[features[f] for f in EARLY_WARNING_FEATURE_NAMES]], dtype=np.float32)
        result: dict[str, Any] = {"features": features}

        # Isolation Forest anomaly score
        if if_model and scaler:
            scaled = scaler.transform(feature_vec)
            raw_score = if_model.decision_function(scaled)[0]
            # Normalise (lower decision_function = more anomalous)
            anomaly_score = max(0.0, min(1.0, 0.5 - raw_score))
            is_anomaly = bool(if_model.predict(scaled)[0] == -1)
            result["anomaly_score"] = round(float(anomaly_score), 4)
            result["is_anomaly"] = is_anomaly
        else:
            anomaly_score = 0.5
            result["anomaly_score"] = 0.5
            result["is_anomaly"] = False

        # Phase B: Severity classification
        if lgb_model:
            # Add anomaly score as extra feature
            feature_vec_full = np.append(feature_vec[0], anomaly_score).reshape(1, -1)
            proba = lgb_model.predict_proba(feature_vec_full)[0]
            predicted = int(np.argmax(proba))
            result["severity"] = SEVERITY_LABELS[predicted]
            result["severity_probabilities"] = {
                label: round(float(proba[i]), 4)
                for i, label in enumerate(SEVERITY_LABELS)
            }
            result["confidence"] = round(float(np.max(proba)), 4)
        else:
            # Fallback: threshold-based
            if anomaly_score >= 0.8:
                result["severity"] = "CRITICAL"
            elif anomaly_score >= 0.5:
                result["severity"] = "WARNING"
            else:
                result["severity"] = "INFO"
            result["confidence"] = 0.5

        results.append(result)

    return results


def output_fn(prediction: list[dict], accept: str = "application/json") -> str:
    if accept == "application/json":
        return json.dumps(prediction, default=str)
    raise ValueError(f"Unsupported: {accept}")
