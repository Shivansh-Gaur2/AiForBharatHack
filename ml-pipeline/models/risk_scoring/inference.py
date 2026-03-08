"""XGBoost risk model – SageMaker inference handler.

This script is deployed as the ``inference.py`` alongside the model artefact.
SageMaker invokes ``model_fn``, ``input_fn``, ``predict_fn``, ``output_fn``
as the standard serving contract.

Returns both classification probabilities and regression score for each input.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

import numpy as np
import xgboost as xgb

logger = logging.getLogger(__name__)

CATEGORY_LABELS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


# ---------------------------------------------------------------------------
# SageMaker serving functions
# ---------------------------------------------------------------------------

def model_fn(model_dir: str) -> dict[str, xgb.Booster]:
    """Load dual-head models from the model directory."""
    path = pathlib.Path(model_dir)

    classifier = xgb.Booster()
    classifier.load_model(str(path / "risk_classifier.xgb"))

    regressor = xgb.Booster()
    regressor.load_model(str(path / "risk_regressor.xgb"))

    # Load metadata
    meta_path = path / "model_metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    return {
        "classifier": classifier,
        "regressor": regressor,
        "metadata": metadata,
    }


def input_fn(request_body: str, content_type: str = "application/json") -> xgb.DMatrix:
    """Deserialise input into an XGBoost DMatrix."""
    if content_type == "application/json":
        payload = json.loads(request_body)
        instances = payload if isinstance(payload, list) else [payload]

        from data.feature_engineering.risk_features import (
            RISK_FEATURE_NAMES,
            extract_risk_features,
        )

        rows = [extract_risk_features(inst) for inst in instances]
        feature_values = [[row[f] for f in RISK_FEATURE_NAMES] for row in rows]
        data = np.array(feature_values, dtype=np.float32)
        return xgb.DMatrix(data, feature_names=RISK_FEATURE_NAMES)

    elif content_type == "text/csv":
        import pandas as pd
        from io import StringIO

        df = pd.read_csv(StringIO(request_body))
        return xgb.DMatrix(df.values, feature_names=list(df.columns))

    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(
    dmatrix: xgb.DMatrix,
    model: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run dual-head inference (classification + regression)."""
    classifier: xgb.Booster = model["classifier"]
    regressor: xgb.Booster = model["regressor"]

    # Classification probabilities → (N, 4)
    class_probs = classifier.predict(dmatrix)
    if class_probs.ndim == 1:
        class_probs = class_probs.reshape(1, -1)

    # Regression scores → (N,)
    risk_scores = regressor.predict(dmatrix)

    results = []
    for i in range(len(risk_scores)):
        probs = class_probs[i]
        predicted_class = int(np.argmax(probs))
        results.append({
            "risk_score": round(float(risk_scores[i]), 1),
            "risk_category": CATEGORY_LABELS[predicted_class],
            "category_probabilities": {
                label: round(float(probs[j]), 4)
                for j, label in enumerate(CATEGORY_LABELS)
            },
            "confidence": round(float(np.max(probs)), 4),
        })

    return results


def output_fn(prediction: list[dict], accept: str = "application/json") -> str:
    """Serialise prediction results to JSON."""
    if accept == "application/json":
        return json.dumps(prediction, default=str)
    raise ValueError(f"Unsupported accept type: {accept}")
