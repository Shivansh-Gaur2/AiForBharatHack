"""SageMaker-backed cash-flow model – service-side wrapper.

Implements the ``CashFlowModelPredictor`` protocol by calling either
a SageMaker endpoint or loading local Prophet artefacts.

Flag-gated via ``USE_ML_CASHFLOW_MODEL`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import pathlib
from dataclasses import dataclass, field
from typing import Any

import boto3

from services.shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

USE_ML_MODEL = os.environ.get("USE_ML_CASHFLOW_MODEL", "false").lower() == "true"
SAGEMAKER_ENDPOINT = os.environ.get("CASHFLOW_MODEL_ENDPOINT", "rural-credit-cashflow")
LOCAL_MODEL_DIR = os.environ.get("CASHFLOW_MODEL_LOCAL_DIR", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")


@dataclass
class CashFlowPredictionResult:
    """Per-month forecast with uncertainty."""

    monthly_predictions: list[dict[str, float]]
    model_version: str
    cluster_id: int = 0
    confidence: float = 0.0


class SageMakerCashFlowModel:
    """CashFlowModelPredictor backed by SageMaker."""

    def __init__(
        self,
        endpoint_name: str = SAGEMAKER_ENDPOINT,
        region: str = AWS_REGION,
    ) -> None:
        self._endpoint = endpoint_name
        self._client = boto3.client("sagemaker-runtime", region_name=region)
        self._circuit = CircuitBreaker(name="sagemaker-cashflow", failure_threshold=3, recovery_timeout_seconds=60)

    def predict_monthly_flows(
        self,
        historical: list[dict[str, float]],
        horizon_months: int = 12,
        external_factors: dict[str, float] | None = None,
    ) -> CashFlowPredictionResult:
        if not self._circuit.is_call_permitted():
            raise RuntimeError("Circuit breaker OPEN for cashflow model")

        try:
            payload = {
                "horizon_months": horizon_months,
                "regressors": external_factors or {},
            }

            response = self._client.invoke_endpoint(
                EndpointName=self._endpoint,
                ContentType="application/json",
                Body=json.dumps(payload),
            )
            body = json.loads(response["Body"].read().decode())

            self._circuit.record_success()

            return CashFlowPredictionResult(
                monthly_predictions=body if isinstance(body, list) else [body],
                model_version=f"prophet-sagemaker-{self._endpoint}",
            )

        except Exception as e:
            self._circuit.record_failure()
            logger.warning("SageMaker cashflow endpoint failed: %s", e)
            raise

    def get_model_version(self) -> str:
        return f"prophet-sagemaker-{self._endpoint}"


class LocalCashFlowModel:
    """CashFlowModelPredictor backed by local Prophet artefacts."""

    def __init__(self, model_dir: str = LOCAL_MODEL_DIR) -> None:
        self._model_dir = model_dir
        self._models: dict[int, Any] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            path = pathlib.Path(self._model_dir)
            for pkl in path.glob("prophet_cluster_*.pkl"):
                cid = int(pkl.stem.split("_")[-1])
                with open(pkl, "rb") as f:
                    self._models[cid] = pickle.load(f)
            self._loaded = True
            logger.info("Loaded %d local Prophet models", len(self._models))
        except Exception:
            logger.exception("Failed to load local cashflow models")
            raise

    def predict_monthly_flows(
        self,
        historical: list[dict[str, float]],
        horizon_months: int = 12,
        external_factors: dict[str, float] | None = None,
    ) -> CashFlowPredictionResult:
        self._load()

        # Use default cluster (0) or first available
        cluster_id = 0 if 0 in self._models else next(iter(self._models.keys()), 0)
        model = self._models.get(cluster_id)

        if model is None:
            raise RuntimeError("No Prophet model available")

        future = model.make_future_dataframe(periods=horizon_months, freq="MS")

        # Add season regressors
        import numpy as np
        from ml_pipeline.data.feature_engineering.cashflow_features import _month_to_season_flags

        for col in model.extra_regressors:
            if col.startswith("is_"):
                season_idx = {"is_kharif": 0, "is_rabi": 1, "is_zaid": 2}
                seasons = future["ds"].dt.month.apply(_month_to_season_flags)
                future[col] = seasons.apply(lambda x: x[season_idx.get(col, 0)])
            else:
                future[col] = 0.0

        forecast = model.predict(future)
        forecast_period = forecast.tail(horizon_months)

        predictions = []
        for _, row in forecast_period.iterrows():
            predictions.append({
                "date": row["ds"].strftime("%Y-%m-%d"),
                "predicted_income": round(float(row["yhat"]), 2),
                "lower_bound": round(float(row["yhat_lower"]), 2),
                "upper_bound": round(float(row["yhat_upper"]), 2),
            })

        return CashFlowPredictionResult(
            monthly_predictions=predictions,
            model_version="prophet-local",
            cluster_id=cluster_id,
        )

    def get_model_version(self) -> str:
        return "prophet-local"


def get_ml_cashflow_model() -> SageMakerCashFlowModel | LocalCashFlowModel | None:
    """Factory: return cashflow model based on environment config."""
    if not USE_ML_MODEL:
        return None
    if LOCAL_MODEL_DIR:
        return LocalCashFlowModel(LOCAL_MODEL_DIR)
    return SageMakerCashFlowModel()
