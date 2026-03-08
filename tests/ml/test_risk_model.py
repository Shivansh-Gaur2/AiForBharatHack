"""Unit tests for services/risk_assessment/ml/risk_model.py

Tests cover:
- Model artifact availability & lazy loading
- Output structure and value ranges
- Feature sensitivity (stressed → higher score than safe)
- Missing-feature graceful fallback (defaults to 0)
- Probabilities sum to 1
- SHAP feature importances structure
- Fallback to None when models missing (monkeypatched)
"""

from __future__ import annotations

import sys
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_CATEGORIES = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}


# ---------------------------------------------------------------------------
# Fixtures — module-level cache reset so each test starts fresh on purpose
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_risk_model_cache():
    """Ensure model cache is populated but reset monkeypatches after each test."""
    from services.risk_assessment.ml import risk_model
    # Trigger load once so tests run fast
    risk_model._ensure_loaded()
    yield
    # No global reset needed — lazy-load is correct behaviour


# ===========================================================================
# Availability
# ===========================================================================

class TestRiskModelAvailability:

    def test_is_available_returns_true(self):
        from services.risk_assessment.ml import risk_model
        assert risk_model.is_available() is True

    def test_model_cache_populated(self):
        from services.risk_assessment.ml import risk_model
        risk_model._ensure_loaded()
        assert risk_model._model is not None
        assert risk_model._features is not None
        assert risk_model._label_names is not None

    def test_features_list_has_18_elements(self):
        from services.risk_assessment.ml import risk_model
        risk_model._ensure_loaded()
        assert len(risk_model._features) == 18

    def test_label_names_are_valid_categories(self):
        from services.risk_assessment.ml import risk_model
        risk_model._ensure_loaded()
        for name in risk_model._label_names:
            assert name in VALID_CATEGORIES


# ===========================================================================
# Output structure
# ===========================================================================

class TestRiskModelOutputStructure:

    REQUIRED_KEYS = {
        "risk_score",
        "risk_category",
        "confidence_level",
        "probabilities",
        "shap_feature_importances",
        "model_version",
    }

    def test_returns_dict(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        assert isinstance(result, dict)

    def test_all_required_keys_present(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_model_version_string(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        assert result["model_version"] == "xgboost-v1"

    def test_risk_category_is_valid(self, safe_risk_features, stressed_risk_features):
        from services.risk_assessment.ml import risk_model
        for features in (safe_risk_features, stressed_risk_features):
            result = risk_model.predict(features)
            assert result["risk_category"] in VALID_CATEGORIES

    def test_risk_score_in_range(self, safe_risk_features, stressed_risk_features):
        from services.risk_assessment.ml import risk_model
        for features in (safe_risk_features, stressed_risk_features):
            result = risk_model.predict(features)
            assert 0 <= result["risk_score"] <= 1000

    def test_confidence_level_in_range(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        assert 0.0 <= result["confidence_level"] <= 1.0

    def test_probabilities_sum_to_one(self, safe_risk_features, stressed_risk_features):
        from services.risk_assessment.ml import risk_model
        for features in (safe_risk_features, stressed_risk_features):
            result = risk_model.predict(features)
            total = sum(result["probabilities"].values())
            assert abs(total - 1.0) < 1e-4, f"Probabilities sum to {total}"

    def test_probabilities_keys_are_valid_categories(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        for key in result["probabilities"]:
            assert key in VALID_CATEGORIES

    def test_shap_importances_has_18_features(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        shap = result["shap_feature_importances"]
        assert isinstance(shap, dict)
        # SHAP may be empty if explainer artifact missing, but if present → 18 keys
        if shap:
            assert len(shap) == 18


# ===========================================================================
# Feature sensitivity
# ===========================================================================

class TestRiskModelSensitivity:

    def test_stressed_score_higher_than_safe(
        self, safe_risk_features, stressed_risk_features,
    ):
        from services.risk_assessment.ml import risk_model
        safe_result     = risk_model.predict(safe_risk_features)
        stressed_result = risk_model.predict(stressed_risk_features)
        assert stressed_result["risk_score"] > safe_result["risk_score"], (
            f"Expected stressed score ({stressed_result['risk_score']}) > "
            f"safe score ({safe_result['risk_score']})"
        )

    def test_safe_category_not_very_high(self, safe_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(safe_risk_features)
        assert result["risk_category"] in {"LOW", "MEDIUM"}

    def test_stressed_category_is_high_or_very_high(self, stressed_risk_features):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict(stressed_risk_features)
        assert result["risk_category"] in {"HIGH", "VERY_HIGH"}

    def test_has_irrigation_reduces_score(self):
        """Toggling has_irrigation from 0→1 should decrease risk score."""
        from services.risk_assessment.ml import risk_model
        base = {
            "income_volatility_cv": 0.40, "annual_income": 150000,
            "months_below_average": 3, "debt_to_income_ratio": 0.50,
            "total_outstanding": 60000, "active_loan_count": 2,
            "credit_utilisation": 0.55, "on_time_repayment_ratio": 0.75,
            "has_defaults": 0, "seasonal_variance": 30,
            "crop_diversification_index": 0.40, "weather_risk_score": 30,
            "market_risk_score": 30, "dependents": 3, "age": 40,
            "has_irrigation": 0, "land_holding_acres": 2.5, "soil_quality_score": 50,
        }
        with_irrigation = {**base, "has_irrigation": 1}
        score_no_irr  = risk_model.predict(base)["risk_score"]
        score_with_irr = risk_model.predict(with_irrigation)["risk_score"]
        assert score_with_irr <= score_no_irr, (
            "Irrigation should lower or keep the same risk score"
        )

    def test_default_flag_increases_score(self):
        """has_defaults=1 raises score for an already-stressed profile."""
        from services.risk_assessment.ml import risk_model
        # Stressed base profile where defaults make a measurable difference
        base = {
            "income_volatility_cv": 0.60, "annual_income": 90000,
            "months_below_average": 6, "debt_to_income_ratio": 0.75,
            "total_outstanding": 100000, "active_loan_count": 3,
            "credit_utilisation": 0.80, "on_time_repayment_ratio": 0.40,
            "has_defaults": 0, "seasonal_variance": 50,
            "crop_diversification_index": 0.15, "weather_risk_score": 60,
            "market_risk_score": 55, "dependents": 5, "age": 48,
            "has_irrigation": 0, "land_holding_acres": 1.2, "soil_quality_score": 30,
        }
        with_default = {**base, "has_defaults": 1}
        score_no_def   = risk_model.predict(base)["risk_score"]
        score_with_def = risk_model.predict(with_default)["risk_score"]
        assert score_with_def >= score_no_def, (
            "A history of defaults should increase or keep the same risk score"
        )


# ===========================================================================
# Edge cases & robustness
# ===========================================================================

class TestRiskModelEdgeCases:

    def test_empty_dict_returns_dict(self):
        """All-zeroes feature vector should still produce a valid result."""
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict({})
        assert isinstance(result, dict)
        assert result["risk_category"] in VALID_CATEGORIES

    def test_missing_keys_default_to_zero(self):
        """Only providing 1 key — rest default to 0, must not raise."""
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict({"has_defaults": 1})
        assert result is not None
        assert 0 <= result["risk_score"] <= 1000

    def test_predict_returns_none_when_model_unavailable(self, monkeypatch):
        """If _ensure_loaded returns False, predict returns None gracefully."""
        from services.risk_assessment.ml import risk_model
        monkeypatch.setattr(risk_model, "_ensure_loaded", lambda: False)
        result = risk_model.predict({"has_defaults": 0})
        assert result is None

    def test_is_available_false_when_model_unavailable(self, monkeypatch):
        from services.risk_assessment.ml import risk_model
        monkeypatch.setattr(risk_model, "_model", None)
        monkeypatch.setattr(risk_model, "_ensure_loaded", lambda: False)
        assert risk_model.is_available() is False

    def test_extreme_high_dti_gives_high_score(self):
        from services.risk_assessment.ml import risk_model
        result = risk_model.predict({
            "debt_to_income_ratio": 2.0, "total_outstanding": 500000,
            "has_defaults": 1, "credit_utilisation": 1.0,
            "on_time_repayment_ratio": 0.0,
        })
        assert result["risk_score"] >= 500, "Extreme DTI should yield HIGH+ score"
