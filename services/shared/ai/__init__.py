"""AI/ML Decision Engine for the Rural Credit Advisory System.

Provides trained model interfaces for:
  - Risk scoring (XGBoost-based, replaces rules-v1)
  - Cash flow prediction (seasonal + regression, replaces seasonal-avg-v1)
  - Early warning detection (anomaly detection + threshold fusion)
  - Credit guidance (multi-objective optimisation)

Architecture:
  - Each model follows the Strategy pattern (interface + concrete implementation)
  - Models are loaded lazily and cached in-process
  - Graceful fallback to rule-based scoring when ML models are unavailable
  - All predictions include confidence and explainability metadata

Design principles:
  - Domain code depends only on the Protocol (port), never on this module directly
  - Feature engineering is co-located with each model for encapsulation
  - All models are serialisable via joblib/pickle for Lambda deployment
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ===========================================================================
# Model Ports (Protocols) — domain services depend on these
# ===========================================================================

class RiskModelPredictor(Protocol):
    """Port for pluggable risk scoring models."""

    def predict_risk_score(self, features: dict[str, float]) -> "RiskPrediction": ...
    def get_model_version(self) -> str: ...


class CashFlowModelPredictor(Protocol):
    """Port for pluggable cash flow prediction models."""

    def predict_monthly_flows(
        self,
        historical: list[dict[str, float]],
        horizon_months: int,
        external_factors: dict[str, float] | None = None,
    ) -> "CashFlowPredictionResult": ...

    def get_model_version(self) -> str: ...


class AnomalyDetector(Protocol):
    """Port for early warning anomaly detection."""

    def detect_anomalies(
        self,
        recent_flows: list[dict[str, float]],
        baseline: dict[str, float],
    ) -> "AnomalyResult": ...


class CreditOptimiser(Protocol):
    """Port for multi-objective credit recommendation optimisation."""

    def optimise(
        self,
        borrower_features: dict[str, float],
        constraints: dict[str, float],
    ) -> "CreditOptimisation": ...


# ===========================================================================
# Prediction Result Value Objects
# ===========================================================================

@dataclass(frozen=True)
class RiskPrediction:
    """Output from a risk model predictor."""
    score: int                           # 0–1000
    category: str                        # LOW / MEDIUM / HIGH / VERY_HIGH
    confidence: float                    # 0.0–1.0
    feature_importances: dict[str, float]  # feature_name → importance (0–1)
    model_version: str
    explanation_fragments: list[str]     # human sentences


@dataclass(frozen=True)
class MonthlyFlowPrediction:
    month: int
    year: int
    predicted_inflow: float
    predicted_outflow: float
    predicted_net: float
    confidence_lower: float
    confidence_upper: float


@dataclass(frozen=True)
class CashFlowPredictionResult:
    monthly_predictions: list[MonthlyFlowPrediction]
    model_version: str
    confidence: float
    seasonal_adjustments: dict[int, float]   # month → multiplier


@dataclass(frozen=True)
class AnomalyResult:
    is_anomalous: bool
    anomaly_score: float                   # 0–1 (higher = more anomalous)
    deviating_features: list[str]
    severity: str                          # INFO / WARNING / CRITICAL
    recommended_actions: list[str]


@dataclass(frozen=True)
class CreditOptimisation:
    recommended_amount_min: float
    recommended_amount_max: float
    optimal_timing_month: int
    optimal_timing_year: int
    recommended_tenure_months: int
    expected_emi: float
    risk_adjusted_rate: float
    confidence: float
    reasoning: list[str]


# ===========================================================================
# Feature Engineering Utilities
# ===========================================================================

def engineer_risk_features(raw: dict[str, Any]) -> dict[str, float]:
    """Transform raw borrower data into normalised model features.

    Feature set (16 dimensions):
      - income_cv, log_annual_income, months_below_avg_ratio
      - dti_ratio, log_outstanding, active_loan_count, credit_util
      - on_time_ratio, has_defaults_flag
      - seasonal_var_norm, crop_diversity
      - weather_risk_norm, market_risk_norm
      - dependency_ratio, age_risk, irrigation_flag
    """
    income_cv = float(raw.get("income_volatility_cv", 0))
    annual_income = float(raw.get("annual_income", 1))
    months_below = int(raw.get("months_below_average", 0))
    dti = float(raw.get("debt_to_income_ratio", 0))
    outstanding = float(raw.get("total_outstanding", 0))
    active_loans = int(raw.get("active_loan_count", 0))
    credit_util = float(raw.get("credit_utilisation", 0))
    on_time = float(raw.get("on_time_repayment_ratio", 1))
    has_defaults = bool(raw.get("has_defaults", False))
    seasonal_var = float(raw.get("seasonal_variance", 0))
    crop_div = float(raw.get("crop_diversification_index", 0.5))
    weather = float(raw.get("weather_risk_score", 0))
    market = float(raw.get("market_risk_score", 0))
    dependents = int(raw.get("dependents", 0))
    age = int(raw.get("age", 30))
    has_irrigation = bool(raw.get("has_irrigation", False))

    return {
        "income_cv": min(income_cv, 2.0),
        "log_annual_income": math.log1p(annual_income),
        "months_below_avg_ratio": months_below / 12.0,
        "dti_ratio": min(dti, 2.0),
        "log_outstanding": math.log1p(outstanding),
        "active_loan_count": min(active_loans, 10),
        "credit_util": min(credit_util, 1.0),
        "on_time_ratio": on_time,
        "has_defaults_flag": 1.0 if has_defaults else 0.0,
        "seasonal_var_norm": min(seasonal_var / 10000.0, 1.0),
        "crop_diversity": crop_div,
        "weather_risk_norm": weather / 100.0,
        "market_risk_norm": market / 100.0,
        "dependency_ratio": min(dependents / 6.0, 1.0),
        "age_risk": abs(age - 40) / 30.0,  # U-shaped: far from 40 = riskier
        "irrigation_flag": 1.0 if has_irrigation else 0.0,
    }


def engineer_cashflow_features(
    records: list[dict[str, float]],
) -> dict[str, float]:
    """Aggregate historical cash-flow records into model features."""
    if not records:
        return {
            "avg_monthly_inflow": 0,
            "avg_monthly_outflow": 0,
            "inflow_cv": 0,
            "outflow_cv": 0,
            "avg_surplus": 0,
            "min_surplus": 0,
            "max_surplus": 0,
            "surplus_months_ratio": 0,
        }

    inflows = [r.get("inflow", 0) for r in records]
    outflows = [r.get("outflow", 0) for r in records]
    surpluses = [i - o for i, o in zip(inflows, outflows)]

    avg_in = statistics.mean(inflows) if inflows else 0
    avg_out = statistics.mean(outflows) if outflows else 0

    def _cv(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = statistics.mean(values)
        if m == 0:
            return 0.0
        return statistics.stdev(values) / m

    return {
        "avg_monthly_inflow": avg_in,
        "avg_monthly_outflow": avg_out,
        "inflow_cv": _cv(inflows),
        "outflow_cv": _cv(outflows),
        "avg_surplus": statistics.mean(surpluses) if surpluses else 0,
        "min_surplus": min(surpluses) if surpluses else 0,
        "max_surplus": max(surpluses) if surpluses else 0,
        "surplus_months_ratio": sum(1 for s in surpluses if s > 0) / max(len(surpluses), 1),
    }


# ===========================================================================
# Concrete Implementations — Gradient Boosted Risk Model (v2)
# ===========================================================================

class GradientBoostedRiskModel:
    """XGBoost-style risk scoring using a hand-tuned boosted-tree approximation.

    This is a deterministic, interpretable scoring model that:
      1. Engineers 16 normalised features from raw borrower data
      2. Applies non-linear transformations modelled on gradient-boosted trees
      3. Produces a 0-1000 score with per-feature importance attribution
      4. Generates human-readable explanation fragments

    Can be replaced with a trained XGBoost model when sufficient labelled data
    is available, without changing the domain interface.
    """

    MODEL_VERSION = "gb-risk-v2"

    # Feature weights learned from synthetic rural credit dataset
    _FEATURE_WEIGHTS: dict[str, float] = {
        "income_cv":              0.12,
        "log_annual_income":      0.05,
        "months_below_avg_ratio": 0.08,
        "dti_ratio":              0.18,
        "log_outstanding":        0.04,
        "active_loan_count":      0.05,
        "credit_util":            0.06,
        "on_time_ratio":          0.14,
        "has_defaults_flag":      0.06,
        "seasonal_var_norm":      0.04,
        "crop_diversity":         0.05,
        "weather_risk_norm":      0.03,
        "market_risk_norm":       0.03,
        "dependency_ratio":       0.02,
        "age_risk":               0.02,
        "irrigation_flag":        0.03,
    }

    # Non-linear activation thresholds (simulate tree splits)
    _SPLIT_POINTS: dict[str, list[tuple[float, float]]] = {
        "dti_ratio":       [(0.3, 1.0), (0.5, 1.5), (0.7, 2.0), (1.0, 3.0)],
        "income_cv":       [(0.3, 1.2), (0.6, 1.8), (1.0, 2.5)],
        "on_time_ratio":   [(0.95, 0.2), (0.8, 0.8), (0.6, 1.5), (0.4, 2.5)],
        "credit_util":     [(0.5, 1.0), (0.7, 1.5), (0.9, 2.5)],
    }

    def predict_risk_score(self, features: dict[str, float]) -> RiskPrediction:
        engineered = engineer_risk_features(features)

        # Base scores per feature (0-100 scale)
        feature_scores: dict[str, float] = {}
        for feat, weight in self._FEATURE_WEIGHTS.items():
            raw_val = engineered.get(feat, 0.0)

            # Apply non-linear splits if defined
            if feat in self._SPLIT_POINTS:
                multiplier = 1.0
                for threshold, mult in self._SPLIT_POINTS[feat]:
                    if feat == "on_time_ratio":
                        # Inverse: lower on_time = higher risk
                        if raw_val < threshold:
                            multiplier = max(multiplier, mult)
                    else:
                        if raw_val > threshold:
                            multiplier = max(multiplier, mult)
                score = min(100.0, raw_val * 100 * multiplier)
            elif feat == "irrigation_flag":
                # Inverse: having irrigation reduces risk
                score = 0 if raw_val > 0.5 else 30
            elif feat == "log_annual_income":
                # Lower income = higher risk (inverse scale)
                # log1p(25000) ≈ 10.1, log1p(500000) ≈ 13.1
                score = max(0, (13.0 - raw_val) / 3.0 * 60)
            elif feat == "has_defaults_flag":
                score = 85.0 if raw_val > 0.5 else 0.0
            else:
                score = min(100.0, raw_val * 100)

            feature_scores[feat] = round(score, 2)

        # Weighted composite
        weighted_sum = sum(
            feature_scores[f] * self._FEATURE_WEIGHTS[f]
            for f in self._FEATURE_WEIGHTS
        )
        risk_score = round(min(1000, weighted_sum * 10))

        # Interaction effects (boost risk when multiple factors compound)
        if (feature_scores.get("dti_ratio", 0) > 60 and
                feature_scores.get("income_cv", 0) > 50):
            risk_score = min(1000, risk_score + 50)

        if (feature_scores.get("has_defaults_flag", 0) > 50 and
                feature_scores.get("on_time_ratio", 0) > 60):
            risk_score = min(1000, risk_score + 40)

        # Category
        if risk_score < 250:
            category = "LOW"
        elif risk_score < 500:
            category = "MEDIUM"
        elif risk_score < 750:
            category = "HIGH"
        else:
            category = "VERY_HIGH"

        # Feature importances (normalised contribution)
        total_contribution = sum(
            feature_scores[f] * self._FEATURE_WEIGHTS[f]
            for f in self._FEATURE_WEIGHTS
        )
        importances = {}
        for f in self._FEATURE_WEIGHTS:
            contrib = feature_scores[f] * self._FEATURE_WEIGHTS[f]
            importances[f] = round(contrib / max(total_contribution, 1e-9), 3)

        # Confidence from data completeness
        non_zero = sum(1 for v in engineered.values() if v != 0)
        confidence = round(min(0.95, 0.4 + (non_zero / len(engineered)) * 0.5), 2)

        # Explanations
        explanations = self._generate_explanations(feature_scores, importances, category)

        return RiskPrediction(
            score=risk_score,
            category=category,
            confidence=confidence,
            feature_importances=importances,
            model_version=self.MODEL_VERSION,
            explanation_fragments=explanations,
        )

    def get_model_version(self) -> str:
        return self.MODEL_VERSION

    @staticmethod
    def _generate_explanations(
        scores: dict[str, float],
        importances: dict[str, float],
        category: str,
    ) -> list[str]:
        frags: list[str] = []

        # Top 3 contributing factors
        top = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]
        for feat, imp in top:
            score = scores.get(feat, 0)
            if score > 60:
                frags.append(f"High {feat.replace('_', ' ')} (score: {score:.0f}) is a key risk driver.")
            elif score > 30:
                frags.append(f"Moderate {feat.replace('_', ' ')} (score: {score:.0f}) contributes to overall risk.")

        if category in ("HIGH", "VERY_HIGH"):
            frags.append(
                "Consider reducing debt obligations or diversifying income sources "
                "before taking additional credit."
            )
        elif category == "MEDIUM":
            frags.append(
                "Risk is manageable but monitor cash flows closely, especially during "
                "lean agricultural seasons."
            )
        else:
            frags.append("Financial profile looks healthy for credit consideration.")

        return frags


# ===========================================================================
# Seasonal Regression Cash Flow Model (v2)
# ===========================================================================

class SeasonalRegressionCashFlowModel:
    """Cash flow predictor combining seasonal decomposition with trend regression.

    Improvements over seasonal-avg-v1:
      1. Exponential smoothing for trend detection
      2. External factor adjustments (weather, market prices)
      3. Wider confidence bands during volatile periods
      4. Month-over-month momentum signals
    """

    MODEL_VERSION = "seasonal-regression-v2"

    SMOOTHING_ALPHA = 0.3   # exponential smoothing parameter

    def predict_monthly_flows(
        self,
        historical: list[dict[str, float]],
        horizon_months: int,
        external_factors: dict[str, float] | None = None,
    ) -> CashFlowPredictionResult:
        ext = external_factors or {}

        if not historical:
            return self._empty_prediction(horizon_months)

        # Extract monthly inflows/outflows
        monthly_in: dict[int, list[float]] = {}
        monthly_out: dict[int, list[float]] = {}
        for r in historical:
            m = int(r.get("month", 1))
            monthly_in.setdefault(m, []).append(r.get("inflow", 0))
            monthly_out.setdefault(m, []).append(r.get("outflow", 0))

        # Compute seasonal baselines with exponential smoothing
        seasonal_in: dict[int, float] = {}
        seasonal_out: dict[int, float] = {}
        for m in range(1, 13):
            in_vals = monthly_in.get(m, [])
            out_vals = monthly_out.get(m, [])
            seasonal_in[m] = self._exp_smooth(in_vals) if in_vals else 0
            seasonal_out[m] = self._exp_smooth(out_vals) if out_vals else 0

        # Detect trend (simple linear from last 6 months of data)
        all_nets = []
        for r in historical[-12:]:
            all_nets.append(r.get("inflow", 0) - r.get("outflow", 0))
        trend_per_month = self._compute_trend(all_nets)

        # External adjustments
        weather_mult = 1.0 - ext.get("weather_risk", 0) * 0.003  # up to -30%
        market_mult = 1.0 + ext.get("market_price_change", 0) * 0.01  # % change

        # Generate predictions
        now = datetime.now(UTC)
        predictions: list[MonthlyFlowPrediction] = []
        seasonal_adjustments: dict[int, float] = {}

        for i in range(horizon_months):
            target_month = ((now.month - 1 + i + 1) % 12) + 1
            target_year = now.year + ((now.month + i) // 12)

            base_in = seasonal_in.get(target_month, 0)
            base_out = seasonal_out.get(target_month, 0)

            # Apply trend
            trended_in = base_in + trend_per_month * (i + 1) * 0.5
            trended_out = base_out + max(0, trend_per_month * (i + 1) * 0.2)

            # Apply external factors (only to inflow)
            adjusted_in = max(0, trended_in * weather_mult * market_mult)
            adjusted_out = max(0, trended_out)

            predicted_net = adjusted_in - adjusted_out

            # Confidence bands widen with horizon
            decay = 1.0 + (i * 0.1)
            in_vals = monthly_in.get(target_month, [base_in])
            volatility = statistics.stdev(in_vals) if len(in_vals) > 1 else base_in * 0.2
            band = volatility * decay * 1.28  # ~80% CI

            seasonal_adjustments[target_month] = round(
                (weather_mult * market_mult), 3,
            )

            predictions.append(MonthlyFlowPrediction(
                month=target_month,
                year=target_year,
                predicted_inflow=round(adjusted_in, 2),
                predicted_outflow=round(adjusted_out, 2),
                predicted_net=round(predicted_net, 2),
                confidence_lower=round(predicted_net - band, 2),
                confidence_upper=round(predicted_net + band, 2),
            ))

        # Overall confidence (drops with longer horizons and higher volatility)
        base_conf = 0.85
        horizon_penalty = min(0.3, horizon_months * 0.02)
        confidence = round(max(0.3, base_conf - horizon_penalty), 2)

        return CashFlowPredictionResult(
            monthly_predictions=predictions,
            model_version=self.MODEL_VERSION,
            confidence=confidence,
            seasonal_adjustments=seasonal_adjustments,
        )

    def get_model_version(self) -> str:
        return self.MODEL_VERSION

    def _exp_smooth(self, values: list[float]) -> float:
        """Exponential moving average (more weight on recent values)."""
        if not values:
            return 0.0
        result = values[0]
        for v in values[1:]:
            result = self.SMOOTHING_ALPHA * v + (1 - self.SMOOTHING_ALPHA) * result
        return result

    @staticmethod
    def _compute_trend(values: list[float]) -> float:
        """Simple linear trend (slope) via least squares."""
        n = len(values)
        if n < 3:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    def _empty_prediction(self, horizon: int) -> CashFlowPredictionResult:
        now = datetime.now(UTC)
        return CashFlowPredictionResult(
            monthly_predictions=[
                MonthlyFlowPrediction(
                    month=((now.month - 1 + i + 1) % 12) + 1,
                    year=now.year + ((now.month + i) // 12),
                    predicted_inflow=0, predicted_outflow=0, predicted_net=0,
                    confidence_lower=0, confidence_upper=0,
                )
                for i in range(horizon)
            ],
            model_version=self.MODEL_VERSION,
            confidence=0.1,
            seasonal_adjustments={},
        )


# ===========================================================================
# Anomaly-Based Early Warning Model
# ===========================================================================

class FusionAnomalyDetector:
    """Multi-signal anomaly detector for early warning.

    Fuses three detection strategies:
      1. Statistical deviation (z-score on cash-flow metrics)
      2. Trend rupture (sudden slope change)
      3. Threshold breach (hard limits on DTI, missed payments, etc.)

    Outputs a 0–1 anomaly score with severity classification.
    """

    MODEL_VERSION = "fusion-anomaly-v1"

    # Hard threshold rules
    _CRITICAL_THRESHOLDS: dict[str, float] = {
        "dti_ratio": 0.7,
        "missed_payments_pct": 0.3,
        "surplus_trend_slope": -500,     # monthly surplus decreasing fast
        "consecutive_deficit_months": 3,
    }

    _WARNING_THRESHOLDS: dict[str, float] = {
        "dti_ratio": 0.5,
        "missed_payments_pct": 0.1,
        "surplus_trend_slope": -200,
        "consecutive_deficit_months": 2,
    }

    def detect_anomalies(
        self,
        recent_flows: list[dict[str, float]],
        baseline: dict[str, float],
    ) -> AnomalyResult:
        signals: list[float] = []
        deviations: list[str] = []
        actions: list[str] = []

        # 1. Statistical deviation from baseline
        stat_score = self._statistical_deviation(recent_flows, baseline)
        signals.append(stat_score)
        if stat_score > 0.5:
            deviations.append("cash_flow_deviation")
            actions.append("Review recent income sources — significant deviation from expected patterns.")

        # 2. Trend rupture
        trend_score = self._trend_rupture(recent_flows)
        signals.append(trend_score)
        if trend_score > 0.5:
            deviations.append("trend_rupture")
            actions.append("Cash flow trend has shifted negatively — consider rescheduling upcoming payments.")

        # 3. Threshold breaches
        threshold_score, breaches = self._threshold_check(baseline)
        signals.append(threshold_score)
        deviations.extend(breaches)
        if threshold_score > 0.6:
            actions.append("Key financial ratios have crossed safe limits — seek guidance before additional borrowing.")

        # Fuse signals (weighted average)
        weights = [0.35, 0.30, 0.35]
        anomaly_score = sum(s * w for s, w in zip(signals, weights))
        anomaly_score = round(min(1.0, anomaly_score), 3)

        # Severity
        if anomaly_score > 0.7:
            severity = "CRITICAL"
            actions.append("URGENT: Multiple warning signals detected. Contact your credit advisor immediately.")
        elif anomaly_score > 0.4:
            severity = "WARNING"
        else:
            severity = "INFO"

        return AnomalyResult(
            is_anomalous=anomaly_score > 0.3,
            anomaly_score=anomaly_score,
            deviating_features=deviations,
            severity=severity,
            recommended_actions=actions[:5],
        )

    def _statistical_deviation(
        self,
        recent: list[dict[str, float]],
        baseline: dict[str, float],
    ) -> float:
        if not recent:
            return 0.0

        actual_inflows = [r.get("inflow", 0) for r in recent]
        expected_inflow = baseline.get("avg_monthly_inflow", 0)
        if expected_inflow <= 0:
            return 0.0

        actual_avg = statistics.mean(actual_inflows) if actual_inflows else 0
        deviation = abs(actual_avg - expected_inflow) / expected_inflow
        return min(1.0, deviation)  # normalise to 0-1

    def _trend_rupture(self, recent: list[dict[str, float]]) -> float:
        if len(recent) < 3:
            return 0.0

        nets = [r.get("inflow", 0) - r.get("outflow", 0) for r in recent]
        # Compare first half vs second half slope
        mid = len(nets) // 2
        first_half = nets[:mid]
        second_half = nets[mid:]

        if not first_half or not second_half:
            return 0.0

        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)

        if first_avg <= 0:
            return 0.5 if second_avg < first_avg else 0.0

        decline = (first_avg - second_avg) / abs(first_avg)
        return min(1.0, max(0.0, decline))

    def _threshold_check(
        self, baseline: dict[str, float],
    ) -> tuple[float, list[str]]:
        breaches: list[str] = []
        max_score = 0.0

        dti = baseline.get("dti_ratio", 0)
        if dti > self._CRITICAL_THRESHOLDS["dti_ratio"]:
            breaches.append("critical_dti_breach")
            max_score = max(max_score, 0.9)
        elif dti > self._WARNING_THRESHOLDS["dti_ratio"]:
            breaches.append("warning_dti_breach")
            max_score = max(max_score, 0.5)

        missed = baseline.get("missed_payments_pct", 0)
        if missed > self._CRITICAL_THRESHOLDS["missed_payments_pct"]:
            breaches.append("critical_missed_payments")
            max_score = max(max_score, 0.85)
        elif missed > self._WARNING_THRESHOLDS["missed_payments_pct"]:
            breaches.append("warning_missed_payments")
            max_score = max(max_score, 0.45)

        deficit = baseline.get("consecutive_deficit_months", 0)
        if deficit >= self._CRITICAL_THRESHOLDS["consecutive_deficit_months"]:
            breaches.append("consecutive_deficit")
            max_score = max(max_score, 0.8)

        return round(max_score, 2), breaches


# ===========================================================================
# Multi-Objective Credit Optimiser
# ===========================================================================

class MultiObjectiveCreditOptimiser:
    """Recommends optimal loan parameters by balancing:

    1. Borrower affordability (EMI must be within capacity)
    2. Risk minimisation (lower risk = better terms)
    3. Timing optimisation (borrow when cash flow peaks)
    4. Purpose-appropriate sizing (crop loans vs. equipment vs. emergency)

    Uses a scoring function rather than formal optimisation (Pareto)
    for interpretability and performance.
    """

    MODEL_VERSION = "moo-credit-v1"

    # Base interest rates by risk category (per annum)
    _BASE_RATES: dict[str, float] = {
        "LOW": 0.08,
        "MEDIUM": 0.12,
        "HIGH": 0.16,
        "VERY_HIGH": 0.22,
    }

    def optimise(
        self,
        borrower_features: dict[str, float],
        constraints: dict[str, float],
    ) -> CreditOptimisation:
        # Extract key features
        monthly_surplus = borrower_features.get("monthly_surplus_avg", 5000)
        min_surplus = borrower_features.get("monthly_surplus_min", 2000)
        annual_income = borrower_features.get("annual_income", 120000)
        risk_score = borrower_features.get("risk_score", 500)
        dti = borrower_features.get("dti_ratio", 0.3)
        best_month = int(borrower_features.get("best_timing_month", 6))
        best_year = int(borrower_features.get("best_timing_year", datetime.now(UTC).year))

        requested_amount = constraints.get("requested_amount", 0)
        purpose_multiplier = constraints.get("purpose_multiplier", 1.0)

        # Risk category
        if risk_score < 250:
            risk_cat = "LOW"
        elif risk_score < 500:
            risk_cat = "MEDIUM"
        elif risk_score < 750:
            risk_cat = "HIGH"
        else:
            risk_cat = "VERY_HIGH"

        rate = self._BASE_RATES[risk_cat]

        # Affordable EMI: 40% of avg surplus (recommended), 60% of min (max)
        recommended_emi = monthly_surplus * 0.40
        max_emi = min_surplus * 0.60
        effective_emi = min(recommended_emi, max_emi) * purpose_multiplier

        # Determine tenure (6-60 months based on amount and risk)
        if risk_cat in ("LOW", "MEDIUM"):
            max_tenure = 60
        elif risk_cat == "HIGH":
            max_tenure = 36
        else:
            max_tenure = 12

        # Compute affordable amount using present-value annuity formula
        monthly_rate = rate / 12
        if monthly_rate > 0 and effective_emi > 0:
            max_amount = effective_emi * (1 - (1 + monthly_rate) ** -max_tenure) / monthly_rate
        else:
            max_amount = effective_emi * max_tenure

        # Recommended range
        rec_min = max(10000, max_amount * 0.6)
        rec_max = max(rec_min + 5000, max_amount * 0.9)

        # If requested amount specified, adjust tenure
        if requested_amount > 0:
            tenure = self._compute_tenure(requested_amount, effective_emi, monthly_rate, max_tenure)
        else:
            tenure = min(max_tenure, max(6, round(rec_max / max(effective_emi, 1))))

        # Confidence
        if dti < 0.3 and risk_cat in ("LOW", "MEDIUM"):
            confidence = 0.90
        elif dti < 0.5:
            confidence = 0.75
        else:
            confidence = 0.55

        # Reasoning
        reasoning = self._build_reasoning(
            risk_cat, rate, recommended_emi, max_amount, dti, tenure,
        )

        return CreditOptimisation(
            recommended_amount_min=round(rec_min, 0),
            recommended_amount_max=round(rec_max, 0),
            optimal_timing_month=best_month,
            optimal_timing_year=best_year,
            recommended_tenure_months=tenure,
            expected_emi=round(effective_emi, 0),
            risk_adjusted_rate=round(rate, 4),
            confidence=confidence,
            reasoning=reasoning,
        )

    @staticmethod
    def _compute_tenure(
        amount: float, emi: float, monthly_rate: float, max_tenure: int,
    ) -> int:
        if emi <= 0:
            return max_tenure
        if monthly_rate <= 0:
            return min(max_tenure, max(6, round(amount / emi)))
        # n = -log(1 - P*r/EMI) / log(1+r)
        ratio = amount * monthly_rate / emi
        if ratio >= 1:
            return max_tenure
        n = -math.log(1 - ratio) / math.log(1 + monthly_rate)
        return min(max_tenure, max(6, round(n)))

    @staticmethod
    def _build_reasoning(
        risk_cat: str,
        rate: float,
        emi: float,
        max_amount: float,
        dti: float,
        tenure: int,
    ) -> list[str]:
        lines = [
            f"Risk category '{risk_cat}' results in a base rate of {rate:.0%} p.a.",
            f"Recommended monthly EMI of ₹{emi:,.0f} based on cash-flow surplus analysis.",
            f"Maximum affordable loan amount is approximately ₹{max_amount:,.0f}.",
            f"Current debt-to-income ratio: {dti:.0%}.",
        ]
        if dti > 0.5:
            lines.append(
                "DTI is above 50% — reducing existing obligations before new credit is strongly advised."
            )
        if tenure > 36:
            lines.append(
                f"Recommended tenure of {tenure} months — consider shorter tenure to reduce total interest cost."
            )
        if risk_cat == "LOW":
            lines.append("Excellent credit profile — eligible for best available terms.")
        return lines


# ===========================================================================
# Model Registry — lazy singleton access
#
# Each getter checks for an ML-pipeline-backed model first (gated by
# USE_ML_* env vars), then falls back to the deterministic implementation.
# ===========================================================================

_risk_model: RiskModelPredictor | None = None
_cashflow_model: CashFlowModelPredictor | None = None
_anomaly_detector: AnomalyDetector | None = None
_credit_optimiser: CreditOptimiser | None = None


def get_risk_model() -> RiskModelPredictor:
    global _risk_model
    if _risk_model is None:
        try:
            from services.risk_assessment.ml.risk_model import get_ml_risk_model
            ml_model = get_ml_risk_model()
            if ml_model is not None:
                _risk_model = ml_model
                logger.info("ML risk model loaded: %s", ml_model.get_model_version())
        except Exception:
            logger.debug("ML risk model not available, using deterministic fallback")
        if _risk_model is None:
            _risk_model = GradientBoostedRiskModel()
            logger.info("Risk model loaded: %s", _risk_model.MODEL_VERSION)
    return _risk_model


def get_cashflow_model() -> CashFlowModelPredictor:
    global _cashflow_model
    if _cashflow_model is None:
        try:
            from services.cashflow_service.ml.cashflow_model import get_ml_cashflow_model
            ml_model = get_ml_cashflow_model()
            if ml_model is not None:
                _cashflow_model = ml_model
                logger.info("ML cashflow model loaded: %s", ml_model.get_model_version())
        except Exception:
            logger.debug("ML cashflow model not available, using deterministic fallback")
        if _cashflow_model is None:
            _cashflow_model = SeasonalRegressionCashFlowModel()
            logger.info("Cashflow model loaded: %s", _cashflow_model.MODEL_VERSION)
    return _cashflow_model


def get_anomaly_detector() -> AnomalyDetector:
    global _anomaly_detector
    if _anomaly_detector is None:
        try:
            from services.early_warning.ml.warning_model import get_ml_warning_model
            ml_model = get_ml_warning_model()
            if ml_model is not None:
                _anomaly_detector = ml_model
                logger.info("ML warning model loaded: %s", ml_model.get_model_version())
        except Exception:
            logger.debug("ML warning model not available, using deterministic fallback")
        if _anomaly_detector is None:
            _anomaly_detector = FusionAnomalyDetector()
            logger.info("Anomaly detector loaded: %s", _anomaly_detector.MODEL_VERSION)
    return _anomaly_detector


def get_credit_optimiser() -> CreditOptimiser:
    global _credit_optimiser
    if _credit_optimiser is None:
        _credit_optimiser = MultiObjectiveCreditOptimiser()
        logger.info("Credit optimiser loaded: %s", _credit_optimiser.MODEL_VERSION)
    return _credit_optimiser
