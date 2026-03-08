"""Tests for service-side ML wrappers.

Validates the SageMaker and local model wrappers, factory functions,
and circuit breaker integration.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Risk model wrapper
# ---------------------------------------------------------------------------


class TestRiskModelWrapper:
    def test_factory_returns_none_when_disabled(self):
        with patch.dict(os.environ, {"USE_ML_RISK_MODEL": "false"}, clear=False):
            from services.risk_assessment.ml.risk_model import get_ml_risk_model
            # Reload to pick up env change
            import importlib
            import services.risk_assessment.ml.risk_model as mod
            importlib.reload(mod)
            assert mod.get_ml_risk_model() is None

    def test_factory_returns_local_when_dir_set(self, tmp_path):
        with patch.dict(os.environ, {
            "USE_ML_RISK_MODEL": "true",
            "RISK_MODEL_LOCAL_DIR": str(tmp_path),
        }, clear=False):
            import importlib
            import services.risk_assessment.ml.risk_model as mod
            importlib.reload(mod)
            model = mod.get_ml_risk_model()
            assert model is not None
            assert isinstance(model, mod.LocalRiskModel)

    def test_factory_returns_sagemaker_when_no_dir(self):
        with patch.dict(os.environ, {
            "USE_ML_RISK_MODEL": "true",
            "RISK_MODEL_LOCAL_DIR": "",
        }, clear=False):
            import importlib
            import services.risk_assessment.ml.risk_model as mod
            importlib.reload(mod)
            model = mod.get_ml_risk_model()
            assert model is not None
            assert isinstance(model, mod.SageMakerRiskModel)

    def test_sagemaker_invoke_success(self):
        from services.risk_assessment.ml.risk_model import (
            RiskPredictionResult,
            SageMakerRiskModel,
        )

        model = SageMakerRiskModel.__new__(SageMakerRiskModel)
        mock_client = MagicMock()
        mock_response = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({
                "risk_score": 350,
                "risk_category": "MEDIUM",
                "confidence": 0.82,
                "category_probabilities": {"LOW": 0.1, "MEDIUM": 0.82, "HIGH": 0.06, "VERY_HIGH": 0.02},
            }).encode()))
        }
        mock_client.invoke_endpoint.return_value = mock_response

        from services.shared.circuit_breaker import CircuitBreaker
        model._client = mock_client
        model._endpoint = "test-endpoint"
        model._circuit = CircuitBreaker(name="test", failure_threshold=3)

        result = model.predict_risk_score({"income_cv": 0.3, "dti_ratio": 0.5})
        assert isinstance(result, RiskPredictionResult)
        assert result.score == 350
        assert result.category == "MEDIUM"
        assert result.confidence == 0.82

    def test_sagemaker_circuit_breaker_opens(self):
        from services.risk_assessment.ml.risk_model import SageMakerRiskModel
        from services.shared.circuit_breaker import CircuitBreaker

        model = SageMakerRiskModel.__new__(SageMakerRiskModel)
        mock_client = MagicMock()
        mock_client.invoke_endpoint.side_effect = Exception("endpoint down")

        model._client = mock_client
        model._endpoint = "test-endpoint"
        model._circuit = CircuitBreaker(name="test", failure_threshold=2)

        # Fail twice to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                model.predict_risk_score({"x": 1})

        # Circuit should now be open
        with pytest.raises(RuntimeError, match="Circuit breaker OPEN"):
            model.predict_risk_score({"x": 1})


# ---------------------------------------------------------------------------
# Cashflow model wrapper
# ---------------------------------------------------------------------------


class TestCashflowModelWrapper:
    def test_factory_returns_none_when_disabled(self):
        with patch.dict(os.environ, {"USE_ML_CASHFLOW_MODEL": "false"}, clear=False):
            import importlib
            import services.cashflow_service.ml.cashflow_model as mod
            importlib.reload(mod)
            assert mod.get_ml_cashflow_model() is None

    def test_sagemaker_invoke_success(self):
        from services.cashflow_service.ml.cashflow_model import (
            CashFlowPredictionResult,
            SageMakerCashFlowModel,
        )
        from services.shared.circuit_breaker import CircuitBreaker

        model = SageMakerCashFlowModel.__new__(SageMakerCashFlowModel)
        predictions = [
            {"date": "2024-07-01", "predicted_income": 25000, "lower_bound": 20000, "upper_bound": 30000},
        ]
        mock_client = MagicMock()
        mock_client.invoke_endpoint.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(predictions).encode()))
        }
        model._client = mock_client
        model._endpoint = "test-cashflow"
        model._circuit = CircuitBreaker(name="test", failure_threshold=3)

        result = model.predict_monthly_flows([], horizon_months=12)
        assert isinstance(result, CashFlowPredictionResult)
        assert len(result.monthly_predictions) == 1


# ---------------------------------------------------------------------------
# Warning model wrapper
# ---------------------------------------------------------------------------


class TestWarningModelWrapper:
    def test_factory_returns_none_when_disabled(self):
        with patch.dict(os.environ, {"USE_ML_WARNING_MODEL": "false"}, clear=False):
            import importlib
            import services.early_warning.ml.warning_model as mod
            importlib.reload(mod)
            assert mod.get_ml_warning_model() is None

    def test_sagemaker_invoke_success(self):
        from services.early_warning.ml.warning_model import (
            SageMakerWarningModel,
            WarningPredictionResult,
        )
        from services.shared.circuit_breaker import CircuitBreaker

        model = SageMakerWarningModel.__new__(SageMakerWarningModel)
        mock_client = MagicMock()
        mock_client.invoke_endpoint.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps({
                "is_anomaly": True,
                "anomaly_score": 0.85,
                "severity": "WARNING",
                "confidence": 0.75,
                "severity_probabilities": {"INFO": 0.1, "WARNING": 0.75, "CRITICAL": 0.15},
            }).encode()))
        }
        model._client = mock_client
        model._endpoint = "test-warning"
        model._circuit = CircuitBreaker(name="test", failure_threshold=3)

        result = model.detect(
            profile={"age": 35},
            cashflow_history=[{"income": 1000}],
            loan_data={"emi": 500},
        )
        assert isinstance(result, WarningPredictionResult)
        assert result.is_anomalous is True
        assert result.severity == "WARNING"


# ---------------------------------------------------------------------------
# Shared AI integration
# ---------------------------------------------------------------------------


class TestSharedAIIntegration:
    """Verify the Model Registry getters respect ML flags."""

    def test_get_risk_model_deterministic_by_default(self):
        """Without USE_ML_RISK_MODEL, should return GradientBoostedRiskModel."""
        import importlib
        import services.shared.ai
        import services.risk_assessment.ml.risk_model as rm

        # Reset singleton
        services.shared.ai._risk_model = None

        with patch.dict(os.environ, {"USE_ML_RISK_MODEL": "false"}, clear=False):
            importlib.reload(rm)
            importlib.reload(services.shared.ai)
            model = services.shared.ai.get_risk_model()
            assert hasattr(model, "MODEL_VERSION")
            assert model.MODEL_VERSION == "gb-risk-v2"

    def test_get_risk_model_ml_when_enabled(self):
        """With USE_ML_RISK_MODEL=true, should return ML model."""
        import importlib
        import services.shared.ai
        import services.risk_assessment.ml.risk_model as rm

        services.shared.ai._risk_model = None

        with patch.dict(os.environ, {
            "USE_ML_RISK_MODEL": "true",
            "RISK_MODEL_LOCAL_DIR": "",
        }, clear=False):
            importlib.reload(rm)
            importlib.reload(services.shared.ai)

            model = services.shared.ai.get_risk_model()
            # Should be SageMakerRiskModel
            assert model.get_model_version().startswith("xgboost-sagemaker")
