"""Unit tests for services/early_warning/ml/warning_model.py

Tests cover:
- Model availability (IsolationForest + LightGBM)
- Output structure and value ranges
- Severity ordering: critical features → CRITICAL, safe features → INFO/WARNING
- Anomaly score ordering (stressed > safe)
- Missing features default to 0 without crashing
- Fallback to None when models unavailable
"""

from __future__ import annotations

import pytest

VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}


@pytest.fixture(autouse=True)
def _warmup():
    from services.early_warning.ml import warning_model
    warning_model._ensure_loaded()


# ===========================================================================
# Availability
# ===========================================================================

class TestWarningModelAvailability:

    def test_is_available(self):
        from services.early_warning.ml import warning_model
        assert warning_model.is_available() is True

    def test_iso_forest_loaded(self):
        from services.early_warning.ml import warning_model
        assert warning_model._iso_forest is not None

    def test_lgbm_loaded(self):
        from services.early_warning.ml import warning_model
        assert warning_model._lgbm_clf is not None

    def test_features_list_loaded(self):
        from services.early_warning.ml import warning_model
        assert warning_model._features is not None
        assert len(warning_model._features) == 12


# ===========================================================================
# Output structure
# ===========================================================================

class TestWarningModelOutputStructure:

    REQUIRED_KEYS = {"anomaly_score", "severity", "severity_index", "probability", "model_version"}

    def test_returns_dict(self, safe_ew_features):
        from services.early_warning.ml import warning_model
        result = warning_model.predict(safe_ew_features)
        assert isinstance(result, dict)

    def test_all_required_keys_present(self, safe_ew_features):
        from services.early_warning.ml import warning_model
        result = warning_model.predict(safe_ew_features)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_model_version(self, safe_ew_features):
        from services.early_warning.ml import warning_model
        result = warning_model.predict(safe_ew_features)
        assert result["model_version"] == "isolation-forest+lgbm-v1"

    def test_severity_is_valid(self, safe_ew_features, critical_ew_features):
        from services.early_warning.ml import warning_model
        for features in (safe_ew_features, critical_ew_features):
            result = warning_model.predict(features)
            assert result["severity"] in VALID_SEVERITIES

    def test_severity_index_matches_severity(self, safe_ew_features, critical_ew_features):
        from services.early_warning.ml import warning_model
        for features in (safe_ew_features, critical_ew_features):
            result = warning_model.predict(features)
            expected_idx = warning_model.SEVERITY_NAMES.index(result["severity"])
            assert result["severity_index"] == expected_idx

    def test_anomaly_score_in_range(self, safe_ew_features, critical_ew_features):
        from services.early_warning.ml import warning_model
        for features in (safe_ew_features, critical_ew_features):
            result = warning_model.predict(features)
            assert 0.0 <= result["anomaly_score"] <= 100.0

    def test_probability_in_range(self, safe_ew_features, critical_ew_features):
        from services.early_warning.ml import warning_model
        for features in (safe_ew_features, critical_ew_features):
            result = warning_model.predict(features)
            assert 0.0 <= result["probability"] <= 1.0


# ===========================================================================
# Severity sensitivity
# ===========================================================================

class TestWarningModelSensitivity:

    def test_critical_features_give_critical_or_warning(self, critical_ew_features):
        from services.early_warning.ml import warning_model
        result = warning_model.predict(critical_ew_features)
        assert result["severity"] in {"WARNING", "CRITICAL"}, (
            f"Expected WARNING or CRITICAL for stressed features, got {result['severity']}"
        )

    def test_safe_features_give_info_or_warning(self, safe_ew_features):
        from services.early_warning.ml import warning_model
        result = warning_model.predict(safe_ew_features)
        assert result["severity"] in {"INFO", "WARNING"}, (
            f"Expected INFO or WARNING for safe features, got {result['severity']}"
        )

    def test_critical_severity_index_higher_than_safe(
        self, safe_ew_features, critical_ew_features,
    ):
        from services.early_warning.ml import warning_model
        safe_idx     = warning_model.predict(safe_ew_features)["severity_index"]
        critical_idx = warning_model.predict(critical_ew_features)["severity_index"]
        assert critical_idx >= safe_idx, (
            f"Critical features severity_index ({critical_idx}) should be >= "
            f"safe features ({safe_idx})"
        )

    def test_anomaly_score_higher_for_stressed(self, safe_ew_features, critical_ew_features):
        from services.early_warning.ml import warning_model
        safe_score     = warning_model.predict(safe_ew_features)["anomaly_score"]
        critical_score = warning_model.predict(critical_ew_features)["anomaly_score"]
        assert critical_score >= safe_score, (
            f"Stressed borrower anomaly_score ({critical_score}) should >= "
            f"safe borrower ({safe_score})"
        )

    def test_missed_payments_increases_severity(self):
        """Incrementally adding missed payments should not decrease severity."""
        from services.early_warning.ml import warning_model

        base = {
            "income_deviation_3m": -20, "income_deviation_6m": -15,
            "missed_payments_ytd": 0, "days_overdue_avg": 0,
            "dti_ratio": 0.50, "dti_delta_3m": 0.05,
            "surplus_trend_slope": -200, "weather_shock_score": 30,
            "market_price_shock": -15, "seasonal_stress_flag": 0,
            "risk_category_current": 1, "days_since_last_alert": 30,
        }
        idx_base   = warning_model.predict({**base, "missed_payments_ytd": 0})["severity_index"]
        idx_severe = warning_model.predict({**base, "missed_payments_ytd": 5,
                                            "days_overdue_avg": 60})["severity_index"]
        assert idx_severe >= idx_base


# ===========================================================================
# Edge cases & robustness
# ===========================================================================

class TestWarningModelEdgeCases:

    def test_empty_dict_does_not_raise(self):
        from services.early_warning.ml import warning_model
        result = warning_model.predict({})
        assert isinstance(result, dict)
        assert result["severity"] in VALID_SEVERITIES

    def test_missing_keys_default_zero(self):
        from services.early_warning.ml import warning_model
        result = warning_model.predict({"missed_payments_ytd": 3})
        assert result is not None
        assert result["severity"] in VALID_SEVERITIES

    def test_returns_none_when_unavailable(self, monkeypatch):
        from services.early_warning.ml import warning_model
        monkeypatch.setattr(warning_model, "_ensure_loaded", lambda: False)
        result = warning_model.predict({"missed_payments_ytd": 2})
        assert result is None

    def test_is_available_false_when_patched(self, monkeypatch):
        from services.early_warning.ml import warning_model
        original_iso = warning_model._iso_forest
        monkeypatch.setattr(warning_model, "_iso_forest", None)
        monkeypatch.setattr(warning_model, "_ensure_loaded", lambda: False)
        assert warning_model.is_available() is False
        # Restore
        warning_model._iso_forest = original_iso

    def test_only_days_overdue_set(self):
        """Single extreme feature should not crash inference."""
        from services.early_warning.ml import warning_model
        result = warning_model.predict({"days_overdue_avg": 120.0})
        assert result is not None

    def test_severity_names_constant(self):
        from services.early_warning.ml import warning_model
        assert warning_model.SEVERITY_NAMES == ["INFO", "WARNING", "CRITICAL"]
