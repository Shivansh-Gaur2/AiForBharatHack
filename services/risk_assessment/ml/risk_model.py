"""SageMaker-backed risk model – service-side wrapper.

Implements the ``RiskModelPredictor`` protocol from ``services.shared.ai``
by calling either a SageMaker endpoint (production) or loading a local
artefact (development), with circuit-breaker fallback.

Flag-gated via ``USE_ML_RISK_MODEL`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3

from services.shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

USE_ML_MODEL = os.environ.get("USE_ML_RISK_MODEL", "false").lower() == "true"
SAGEMAKER_ENDPOINT = os.environ.get("RISK_MODEL_ENDPOINT", "rural-credit-risk-scoring")
LOCAL_MODEL_DIR = os.environ.get("RISK_MODEL_LOCAL_DIR", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")


@dataclass
class RiskPredictionResult:
    """Matches the RiskPrediction contract in services.shared.ai."""

    score: int
    category: str
    confidence: float
    model_version: str
    feature_importances: dict[str, float] = field(default_factory=dict)
    explanation_fragments: list[str] = field(default_factory=list)


class SageMakerRiskModel:
    """RiskModelPredictor backed by SageMaker real-time inference.

    Conforms to the ``RiskModelPredictor`` protocol so it can be
    plugged into ``_ai_assess()`` in risk_assessment/domain/services.py.
    """

    def __init__(
        self,
        endpoint_name: str = SAGEMAKER_ENDPOINT,
        region: str = AWS_REGION,
    ) -> None:
        self._endpoint = endpoint_name
        self._client = boto3.client("sagemaker-runtime", region_name=region)
        self._circuit = CircuitBreaker(
            name="sagemaker-risk",
            failure_threshold=3,
            recovery_timeout_seconds=60,
        )

    def predict_risk_score(self, features: dict[str, float]) -> RiskPredictionResult:
        """Invoke SageMaker endpoint for risk scoring."""
        if not self._circuit.is_call_permitted():
            raise RuntimeError("Circuit breaker OPEN for risk model endpoint")

        try:
            response = self._client.invoke_endpoint(
                EndpointName=self._endpoint,
                ContentType="application/json",
                Body=json.dumps(features),
            )
            body = json.loads(response["Body"].read().decode())
            result = body[0] if isinstance(body, list) else body

            self._circuit.record_success()

            return RiskPredictionResult(
                score=int(result.get("risk_score", 500)),
                category=result.get("risk_category", "MEDIUM"),
                confidence=float(result.get("confidence", 0.0)),
                model_version=f"xgboost-sagemaker-{self._endpoint}",
                feature_importances=result.get("category_probabilities", {}),
                explanation_fragments=self._build_explanations(result),
            )

        except Exception as e:
            self._circuit.record_failure()
            logger.warning("SageMaker risk endpoint failed: %s", e)
            raise

    def get_model_version(self) -> str:
        return f"xgboost-sagemaker-{self._endpoint}"

    @staticmethod
    def _build_explanations(result: dict) -> list[str]:
        cat = result.get("risk_category", "MEDIUM")
        score = result.get("risk_score", 0)
        probs = result.get("category_probabilities", {})

        fragments = [
            f"Risk score: {score}/1000 → {cat}",
            f"Classification confidence: {result.get('confidence', 0):.0%}",
        ]

        # Add top category probabilities
        for label, prob in sorted(probs.items(), key=lambda x: -x[1])[:2]:
            fragments.append(f"{label}: {prob:.1%} probability")

        return fragments


class LocalRiskModel:
    """RiskModelPredictor backed by local XGBoost artefacts (dev/test)."""

    def __init__(self, model_dir: str = LOCAL_MODEL_DIR) -> None:
        self._model_dir = model_dir
        self._classifier = None
        self._regressor = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            import pathlib
            import xgboost as xgb

            path = pathlib.Path(self._model_dir)
            self._classifier = xgb.Booster()
            self._classifier.load_model(str(path / "risk_classifier.xgb"))
            self._regressor = xgb.Booster()
            self._regressor.load_model(str(path / "risk_regressor.xgb"))
            self._loaded = True
            logger.info("Loaded local risk models from %s", path)
        except Exception:
            logger.exception("Failed to load local risk models")
            raise

    def predict_risk_score(self, features: dict[str, float]) -> RiskPredictionResult:
        self._load()
        import numpy as np
        import xgboost as xgb

        from ml_pipeline.data.feature_engineering.risk_features import (
            RISK_FEATURE_NAMES,
            extract_risk_features,
        )

        processed = extract_risk_features(features)
        vec = np.array([[processed[f] for f in RISK_FEATURE_NAMES]], dtype=np.float32)
        dmat = xgb.DMatrix(vec, feature_names=RISK_FEATURE_NAMES)

        categories = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
        probs = self._classifier.predict(dmat)[0]
        predicted_idx = int(np.argmax(probs))
        score = int(self._regressor.predict(dmat)[0])

        return RiskPredictionResult(
            score=max(0, min(1000, score)),
            category=categories[predicted_idx],
            confidence=float(np.max(probs)),
            model_version="xgboost-local",
            feature_importances={categories[i]: float(probs[i]) for i in range(4)},
            explanation_fragments=[
                f"Risk score: {score}/1000 → {categories[predicted_idx]}",
                f"Confidence: {float(np.max(probs)):.0%}",
            ],
        )

    def get_model_version(self) -> str:
        return "xgboost-local"


def get_ml_risk_model() -> SageMakerRiskModel | LocalRiskModel | None:
    """Factory: return the appropriate risk model based on environment."""
    if not USE_ML_MODEL:
        return None

    if LOCAL_MODEL_DIR:
        return LocalRiskModel(LOCAL_MODEL_DIR)

    return SageMakerRiskModel()
