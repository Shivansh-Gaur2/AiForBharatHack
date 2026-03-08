"""Tests for ML Pipeline — Evaluation, Bias Detection, Backtesting.

Validates the evaluation quality gates, bias metrics, and backtesting
framework produce correct and consistent results.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Risk evaluation (pure metric functions)
# ---------------------------------------------------------------------------


class TestRiskEvaluation:
    def _make_predictions(self, n: int = 200, accuracy: float = 0.85):
        rng = np.random.default_rng(42)
        y_true = rng.choice([0, 1, 2, 3], size=n, p=[0.3, 0.4, 0.2, 0.1])
        y_pred = y_true.copy()
        n_errors = int(n * (1 - accuracy))
        error_idx = rng.choice(n, n_errors, replace=False)
        y_pred[error_idx] = rng.choice([0, 1, 2, 3], size=n_errors)
        scores_true = rng.integers(100, 900, size=n).astype(float)
        scores_pred = scores_true + rng.normal(0, 30, size=n)
        return y_true, y_pred, scores_true, scores_pred

    def test_compute_risk_metrics_passing(self):
        from evaluation.evaluate_risk import compute_risk_metrics

        y_true, y_pred, st, sp = self._make_predictions(500, 0.90)
        report = compute_risk_metrics(y_true, y_pred, st, sp)

        assert "f1_weighted" in report
        assert "mae" in report
        assert "passed" in report

    def test_compute_risk_metrics_failing(self):
        from evaluation.evaluate_risk import compute_risk_metrics

        rng = np.random.default_rng(99)
        n = 200
        y_true = rng.choice([0, 1, 2, 3], size=n)
        y_pred = rng.choice([0, 1, 2, 3], size=n)
        st = rng.integers(100, 900, size=n).astype(float)
        sp = rng.integers(100, 900, size=n).astype(float)

        report = compute_risk_metrics(y_true, y_pred, st, sp)
        assert report["passed"] is False

    def test_quality_gates_defined(self):
        from evaluation.evaluate_risk import QUALITY_GATES

        assert QUALITY_GATES["f1_weighted_min"] == 0.78
        assert QUALITY_GATES["auc_ovr_min"] == 0.85
        assert QUALITY_GATES["mae_max"] == 80


# ---------------------------------------------------------------------------
# Cashflow evaluation
# ---------------------------------------------------------------------------


class TestCashflowEvaluation:
    def test_compute_cashflow_metrics_passing(self):
        from evaluation.evaluate_cashflow import compute_cashflow_metrics

        rng = np.random.default_rng(42)
        n = 100
        y_true = rng.uniform(10000, 50000, n)
        y_pred = y_true * (1 + rng.normal(0, 0.05, n))

        report = compute_cashflow_metrics(y_true, y_pred)
        assert report["mape"] < 15.0
        assert report["passed"] is True

    def test_compute_cashflow_metrics_failing(self):
        from evaluation.evaluate_cashflow import compute_cashflow_metrics

        rng = np.random.default_rng(42)
        n = 100
        y_true = rng.uniform(10000, 50000, n)
        y_pred = y_true * rng.uniform(0.5, 2.0, n)

        report = compute_cashflow_metrics(y_true, y_pred)
        assert report["passed"] is False


# ---------------------------------------------------------------------------
# Early warning evaluation
# ---------------------------------------------------------------------------


class TestEarlyWarningEvaluation:
    def test_compute_early_warning_metrics_passing(self):
        from evaluation.evaluate_early_warning import compute_early_warning_metrics

        rng = np.random.default_rng(42)
        n = 300
        y_true = rng.choice([0, 1, 2], size=n, p=[0.5, 0.3, 0.2])
        y_pred = y_true.copy()
        errs = rng.choice(n, 30, replace=False)
        y_pred[errs] = rng.choice([0, 1, 2], size=30)
        # Generate anomaly scores correlated with true positive labels
        binary = (y_true >= 1).astype(float)
        scores = binary * 0.7 + rng.uniform(0, 0.3, n)

        report = compute_early_warning_metrics(y_true, y_pred, scores)
        assert "f1_weighted" in report
        assert report["passed"] is True

    def test_compute_early_warning_metrics_failing(self):
        from evaluation.evaluate_early_warning import compute_early_warning_metrics

        rng = np.random.default_rng(42)
        n = 200
        y_true = rng.choice([0, 1, 2], size=n)
        y_pred = rng.choice([0, 1, 2], size=n)
        scores = rng.uniform(0, 1, n)

        report = compute_early_warning_metrics(y_true, y_pred, scores)
        assert report["passed"] is False


# ---------------------------------------------------------------------------
# Bias detection
# ---------------------------------------------------------------------------


class TestBiasDetection:
    def _make_bias_data(self, biased: bool = False):
        rng = np.random.default_rng(42)
        n = 400
        land = rng.choice(
            ["marginal", "small", "medium", "large"],
            size=n, p=[0.4, 0.3, 0.2, 0.1],
        )
        if biased:
            predictions = []
            for la in land:
                if la == "marginal":
                    predictions.append(rng.choice([0, 1], p=[0.3, 0.7]))
                else:
                    predictions.append(rng.choice([0, 1], p=[0.7, 0.3]))
            predictions = np.array(predictions)
        else:
            predictions = rng.choice([0, 1], size=n, p=[0.6, 0.4])

        actuals = rng.choice([0, 1], size=n, p=[0.6, 0.4])
        return land, predictions, actuals

    def test_demographic_parity_structure(self):
        from evaluation.bias_detection import compute_demographic_parity

        land, preds, _ = self._make_bias_data(biased=False)
        result = compute_demographic_parity(preds, land)

        assert "base_rate" in result
        assert "group_rates" in result
        assert "dpl_values" in result
        assert "max_abs_dpl" in result

    def test_demographic_parity_unbiased(self):
        from evaluation.bias_detection import compute_demographic_parity

        land, preds, _ = self._make_bias_data(biased=False)
        result = compute_demographic_parity(preds, land)
        assert result["max_abs_dpl"] < 0.15

    def test_demographic_parity_biased(self):
        from evaluation.bias_detection import compute_demographic_parity

        land, preds, _ = self._make_bias_data(biased=True)
        result = compute_demographic_parity(preds, land)
        assert result["max_abs_dpl"] > 0.10

    def test_equalised_odds_structure(self):
        from evaluation.bias_detection import compute_equalised_odds

        rng = np.random.default_rng(42)
        n = 200
        preds = rng.choice([0, 1, 2], size=n)
        labels = rng.choice([0, 1, 2], size=n)
        groups = rng.choice(["A", "B"], size=n)

        result = compute_equalised_odds(preds, labels, groups)
        assert "A" in result
        assert "B" in result

    def test_run_bias_detection_report(self, tmp_path):
        from evaluation.bias_detection import run_bias_detection

        rng = np.random.default_rng(42)
        n = 300
        preds = rng.choice([0, 1], size=n)
        actuals = rng.choice([0, 1], size=n)
        land_acres = rng.uniform(0, 15, size=n)

        report = run_bias_detection(preds, actuals, land_acres, str(tmp_path))
        assert "demographic_parity" in report
        assert "quality_gate" in report


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------


class TestBacktesting:
    def test_walk_forward_backtest_returns_results(self):
        from evaluation.backtesting import walk_forward_backtest

        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", periods=36, freq="MS")
        df = pd.DataFrame({
            "ds": dates,
            "y": rng.lognormal(10, 0.3, 36),
        })

        def train_fn(train_df):
            return train_df["y"].mean()

        def predict_fn(model, test_df):
            return np.full(len(test_df), model)

        result = walk_forward_backtest(
            df, train_fn, predict_fn,
            initial_train_months=24,
            step_months=1,
            forecast_horizon=3,
        )
        assert "summary" in result
        assert "steps" in result
        assert len(result["steps"]) > 0

    def test_backtest_early_warning(self):
        from evaluation.backtesting import backtest_early_warning

        rng = np.random.default_rng(42)
        n = 200
        df = pd.DataFrame({
            "year": np.repeat(range(2020, 2024), 50),
            "month": rng.integers(1, 13, n),
            "severity": rng.choice(["INFO", "WARNING", "CRITICAL"], n),
            "feature_1": rng.normal(0, 1, n),
            "feature_2": rng.normal(0, 1, n),
        })

        from data.feature_engineering.early_warning_features import SEVERITY_ENCODING

        def train_fn(train_df):
            from sklearn.ensemble import RandomForestClassifier
            X = train_df[["feature_1", "feature_2"]].values
            y = train_df["severity"].map(SEVERITY_ENCODING).astype(int).values
            clf = RandomForestClassifier(n_estimators=10, random_state=42)
            clf.fit(X, y)
            return clf

        def predict_fn(model, test_df):
            X = test_df[["feature_1", "feature_2"]].values
            return model.predict(X)

        result = backtest_early_warning(
            df, train_fn, predict_fn, initial_train_fraction=0.7,
        )
        assert "n_train" in result
        assert "n_test" in result
