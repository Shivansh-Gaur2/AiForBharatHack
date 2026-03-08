"""SageMaker-backed early-warning model – service-side wrapper.

Two-phase pipeline:
  Phase A: Isolation Forest → anomaly_score
  Phase B: LightGBM → severity classification

Flag-gated via ``USE_ML_WARNING_MODEL`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import pickle
from dataclasses import dataclass, field
from typing import Any

import boto3
import numpy as np

from services.shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

USE_ML_MODEL = os.environ.get("USE_ML_WARNING_MODEL", "false").lower() == "true"
SAGEMAKER_ENDPOINT = os.environ.get("WARNING_MODEL_ENDPOINT", "rural-credit-early-warning")
LOCAL_MODEL_DIR = os.environ.get("WARNING_MODEL_LOCAL_DIR", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")


@dataclass
class WarningPredictionResult:
    """Result from the early-warning ML model."""

    is_anomalous: bool
    anomaly_score: float
    severity: str
    confidence: float
    severity_probabilities: dict[str, float] = field(default_factory=dict)
    model_version: str = "unknown"


class SageMakerWarningModel:
    """AnomalyDetector backed by SageMaker endpoint."""

    def __init__(
        self,
        endpoint_name: str = SAGEMAKER_ENDPOINT,
        region: str = AWS_REGION,
    ) -> None:
        self._endpoint = endpoint_name
        self._client = boto3.client("sagemaker-runtime", region_name=region)
        self._circuit = CircuitBreaker(name="sagemaker-warning", failure_threshold=3, recovery_timeout_seconds=60)

    def detect(
        self,
        profile: dict[str, Any],
        cashflow_history: list[dict[str, float]],
        loan_data: dict[str, Any],
        alert_history: list[dict[str, Any]] | None = None,
    ) -> WarningPredictionResult:
        if not self._circuit.is_call_permitted():
            raise RuntimeError("Circuit breaker OPEN for warning model")

        try:
            payload = {
                "profile": profile,
                "cashflow_history": cashflow_history,
                "loan_data": loan_data,
                "alert_history": alert_history or [],
            }

            response = self._client.invoke_endpoint(
                EndpointName=self._endpoint,
                ContentType="application/json",
                Body=json.dumps(payload, default=str),
            )
            body = json.loads(response["Body"].read().decode())
            result = body[0] if isinstance(body, list) else body

            self._circuit.record_success()

            return WarningPredictionResult(
                is_anomalous=result.get("is_anomaly", False),
                anomaly_score=float(result.get("anomaly_score", 0)),
                severity=result.get("severity", "INFO"),
                confidence=float(result.get("confidence", 0)),
                severity_probabilities=result.get("severity_probabilities", {}),
                model_version=f"if-lgb-sagemaker-{self._endpoint}",
            )

        except Exception as e:
            self._circuit.record_failure()
            logger.warning("SageMaker warning endpoint failed: %s", e)
            raise

    def get_model_version(self) -> str:
        return f"if-lgb-sagemaker-{self._endpoint}"


class LocalWarningModel:
    """Warning model backed by local IF + LightGBM artefacts."""

    def __init__(self, model_dir: str = LOCAL_MODEL_DIR) -> None:
        self._model_dir = model_dir
        self._if_model = None
        self._scaler = None
        self._lgb_model = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return

        path = pathlib.Path(self._model_dir)

        # Try loading from subdirectories or flat
        if_dir = path / "isolation_forest" if (path / "isolation_forest").exists() else path
        lgb_dir = path / "lightgbm" if (path / "lightgbm").exists() else path

        try:
            with open(if_dir / "isolation_forest.pkl", "rb") as f:
                self._if_model = pickle.load(f)
            with open(if_dir / "scaler.pkl", "rb") as f:
                self._scaler = pickle.load(f)
            logger.info("Loaded local Isolation Forest model")
        except Exception:
            logger.warning("No local IF model found")

        try:
            with open(lgb_dir / "lightgbm_severity.pkl", "rb") as f:
                self._lgb_model = pickle.load(f)
            logger.info("Loaded local LightGBM model")
        except Exception:
            logger.warning("No local LightGBM model found")

        self._loaded = True

    def detect(
        self,
        profile: dict[str, Any],
        cashflow_history: list[dict[str, float]],
        loan_data: dict[str, Any],
        alert_history: list[dict[str, Any]] | None = None,
    ) -> WarningPredictionResult:
        self._load()

        from ml_pipeline.data.feature_engineering.early_warning_features import (
            EARLY_WARNING_FEATURE_NAMES,
            extract_early_warning_features,
        )

        features = extract_early_warning_features(
            profile, cashflow_history, loan_data, alert_history,
        )
        feature_vec = np.array(
            [[features[f] for f in EARLY_WARNING_FEATURE_NAMES]], dtype=np.float32,
        )

        # Phase A: Anomaly detection
        anomaly_score = 0.5
        is_anomalous = False
        if self._if_model and self._scaler:
            scaled = self._scaler.transform(feature_vec)
            raw = self._if_model.decision_function(scaled)[0]
            anomaly_score = max(0.0, min(1.0, 0.5 - raw))
            is_anomalous = bool(self._if_model.predict(scaled)[0] == -1)

        # Phase B: Severity classification
        severity = "INFO"
        confidence = 0.5
        probs = {}
        if self._lgb_model:
            full_vec = np.append(feature_vec[0], anomaly_score).reshape(1, -1)
            proba = self._lgb_model.predict_proba(full_vec)[0]
            labels = ["INFO", "WARNING", "CRITICAL"]
            predicted = int(np.argmax(proba))
            severity = labels[predicted]
            confidence = float(np.max(proba))
            probs = {labels[i]: float(proba[i]) for i in range(len(labels))}
        elif is_anomalous:
            severity = "CRITICAL" if anomaly_score >= 0.8 else "WARNING"

        return WarningPredictionResult(
            is_anomalous=is_anomalous,
            anomaly_score=round(anomaly_score, 4),
            severity=severity,
            confidence=round(confidence, 4),
            severity_probabilities=probs,
            model_version="if-lgb-local",
        )

    def get_model_version(self) -> str:
        return "if-lgb-local"


def get_ml_warning_model() -> SageMakerWarningModel | LocalWarningModel | None:
    """Factory: return warning model based on environment config."""
    if not USE_ML_MODEL:
        return None
    if LOCAL_MODEL_DIR:
        return LocalWarningModel(LOCAL_MODEL_DIR)
    return SageMakerWarningModel()
