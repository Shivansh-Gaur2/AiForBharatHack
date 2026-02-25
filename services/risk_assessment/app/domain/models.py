"""Risk Assessment domain entities — pure Python, zero infrastructure imports.

Design doc ref: §2 Risk Assessment Service
Properties validated: P8 (Comprehensive Risk Scoring), P9 (Dynamic Risk Updates)

The risk scoring model uses a weighted-factor approach that can later be replaced
with an XGBoost/ML model while keeping the same domain interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from services.shared.models import ProfileId, RiskCategory, generate_id


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
class RiskFactorType(StrEnum):
    INCOME_VOLATILITY = "INCOME_VOLATILITY"
    DEBT_EXPOSURE = "DEBT_EXPOSURE"
    REPAYMENT_HISTORY = "REPAYMENT_HISTORY"
    SEASONAL_RISK = "SEASONAL_RISK"
    WEATHER_RISK = "WEATHER_RISK"
    MARKET_RISK = "MARKET_RISK"
    DEMOGRAPHIC = "DEMOGRAPHIC"
    CROP_DIVERSIFICATION = "CROP_DIVERSIFICATION"


@dataclass(frozen=True)
class RiskFactor:
    """A single contributing factor to the overall risk score."""
    factor_type: RiskFactorType
    score: float              # 0–100 (higher = riskier)
    weight: float             # 0.0–1.0 contribution weight
    description: str
    data_points: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskExplanation:
    """Human-readable explanation of why a risk score was assigned."""
    summary: str
    key_factors: list[str]
    recommendations: list[str]
    confidence_note: str


# ---------------------------------------------------------------------------
# Risk Assessment Aggregate
# ---------------------------------------------------------------------------
@dataclass
class RiskAssessment:
    """Complete risk assessment for a borrower (Aggregate Root)."""
    assessment_id: str
    profile_id: ProfileId
    risk_score: int                    # 0–1000 scale
    risk_category: RiskCategory
    confidence_level: float            # 0.0–1.0
    factors: list[RiskFactor]
    explanation: RiskExplanation
    valid_until: datetime
    created_at: datetime
    updated_at: datetime
    model_version: str = "rules-v1"

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.valid_until

    def get_top_risk_factors(self, n: int = 3) -> list[RiskFactor]:
        """Return the highest-scoring risk factors."""
        return sorted(self.factors, key=lambda f: f.score * f.weight, reverse=True)[:n]


# ---------------------------------------------------------------------------
# Risk Scoring Engine (pure domain logic)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RiskInput:
    """All data needed to compute a risk score (Property 8).

    Must incorporate: income volatility, debt exposure, repayment history,
    and external factors (weather, market).
    """
    profile_id: ProfileId

    # Income
    income_volatility_cv: float          # coefficient of variation
    annual_income: float
    months_below_average: int

    # Debt
    debt_to_income_ratio: float
    total_outstanding: float
    active_loan_count: int
    credit_utilisation: float

    # Repayment history
    on_time_repayment_ratio: float       # 0.0–1.0
    has_defaults: bool

    # Seasonal / external (may be zero if unavailable)
    seasonal_variance: float = 0.0
    crop_diversification_index: float = 0.5  # 0=monoculture, 1=highly diverse
    weather_risk_score: float = 0.0          # 0–100 external weather risk
    market_risk_score: float = 0.0           # 0–100 external market risk

    # Demographics
    dependents: int = 0
    age: int = 30
    has_irrigation: bool = False


# Factor weights (must sum to 1.0)
_FACTOR_WEIGHTS = {
    RiskFactorType.INCOME_VOLATILITY: 0.20,
    RiskFactorType.DEBT_EXPOSURE: 0.25,
    RiskFactorType.REPAYMENT_HISTORY: 0.20,
    RiskFactorType.SEASONAL_RISK: 0.10,
    RiskFactorType.WEATHER_RISK: 0.05,
    RiskFactorType.MARKET_RISK: 0.05,
    RiskFactorType.DEMOGRAPHIC: 0.05,
    RiskFactorType.CROP_DIVERSIFICATION: 0.10,
}

assert abs(sum(_FACTOR_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1"


def _score_income_volatility(inp: RiskInput) -> RiskFactor:
    """Higher CV → higher risk.  CV of 0 → score 0, CV ≥ 1.0 → score 100."""
    score = min(100.0, inp.income_volatility_cv * 100)
    desc = f"Income CV={inp.income_volatility_cv:.2f}"
    if inp.months_below_average > 6:
        score = min(100, score + 10)
        desc += f", {inp.months_below_average} months below average"
    return RiskFactor(
        factor_type=RiskFactorType.INCOME_VOLATILITY,
        score=round(score, 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.INCOME_VOLATILITY],
        description=desc,
        data_points={"cv": inp.income_volatility_cv, "months_below_avg": inp.months_below_average},
    )


def _score_debt_exposure(inp: RiskInput) -> RiskFactor:
    """DTI > 0.5 is risky.  Over-indebtedness when > 0.7."""
    dti_score = min(100.0, inp.debt_to_income_ratio * 125)  # DTI 0.8 → 100
    util_penalty = min(20.0, inp.credit_utilisation * 25)
    count_penalty = min(15.0, max(0, inp.active_loan_count - 2) * 5)
    score = min(100, dti_score + util_penalty + count_penalty)
    return RiskFactor(
        factor_type=RiskFactorType.DEBT_EXPOSURE,
        score=round(score, 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.DEBT_EXPOSURE],
        description=f"DTI={inp.debt_to_income_ratio:.2f}, {inp.active_loan_count} active loans",
        data_points={
            "dti": inp.debt_to_income_ratio,
            "utilisation": inp.credit_utilisation,
            "active_loans": inp.active_loan_count,
        },
    )


def _score_repayment_history(inp: RiskInput) -> RiskFactor:
    """Perfect on-time → 0 risk.  Any default → high risk."""
    base = (1 - inp.on_time_repayment_ratio) * 80
    if inp.has_defaults:
        base = max(base, 70)
    score = min(100, base)
    return RiskFactor(
        factor_type=RiskFactorType.REPAYMENT_HISTORY,
        score=round(score, 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.REPAYMENT_HISTORY],
        description=f"On-time ratio={inp.on_time_repayment_ratio:.0%}, defaults={'yes' if inp.has_defaults else 'no'}",
        data_points={"on_time_ratio": inp.on_time_repayment_ratio, "has_defaults": int(inp.has_defaults)},
    )


def _score_seasonal_risk(inp: RiskInput) -> RiskFactor:
    score = min(100.0, inp.seasonal_variance / 100)  # normalize
    if not inp.has_irrigation:
        score = min(100, score + 15)
    return RiskFactor(
        factor_type=RiskFactorType.SEASONAL_RISK,
        score=round(score, 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.SEASONAL_RISK],
        description=f"Seasonal variance={inp.seasonal_variance:.0f}, irrigation={'yes' if inp.has_irrigation else 'no'}",
        data_points={"seasonal_var": inp.seasonal_variance, "irrigated": int(inp.has_irrigation)},
    )


def _score_weather_risk(inp: RiskInput) -> RiskFactor:
    return RiskFactor(
        factor_type=RiskFactorType.WEATHER_RISK,
        score=round(min(100.0, inp.weather_risk_score), 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.WEATHER_RISK],
        description=f"Weather risk score={inp.weather_risk_score:.0f}",
        data_points={"weather_score": inp.weather_risk_score},
    )


def _score_market_risk(inp: RiskInput) -> RiskFactor:
    return RiskFactor(
        factor_type=RiskFactorType.MARKET_RISK,
        score=round(min(100.0, inp.market_risk_score), 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.MARKET_RISK],
        description=f"Market risk score={inp.market_risk_score:.0f}",
        data_points={"market_score": inp.market_risk_score},
    )


def _score_demographic(inp: RiskInput) -> RiskFactor:
    score = 0.0
    # High dependency burden
    if inp.dependents > 5:
        score += 20
    elif inp.dependents > 3:
        score += 10
    # Age extremes
    if inp.age < 25 or inp.age > 60:
        score += 15
    return RiskFactor(
        factor_type=RiskFactorType.DEMOGRAPHIC,
        score=round(min(100, score), 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.DEMOGRAPHIC],
        description=f"Age={inp.age}, dependents={inp.dependents}",
        data_points={"age": inp.age, "dependents": inp.dependents},
    )


def _score_crop_diversification(inp: RiskInput) -> RiskFactor:
    """Lower diversification → higher risk."""
    score = (1 - inp.crop_diversification_index) * 100
    return RiskFactor(
        factor_type=RiskFactorType.CROP_DIVERSIFICATION,
        score=round(min(100, score), 1),
        weight=_FACTOR_WEIGHTS[RiskFactorType.CROP_DIVERSIFICATION],
        description=f"Diversification index={inp.crop_diversification_index:.2f}",
        data_points={"diversification": inp.crop_diversification_index},
    )


def compute_risk_score(inp: RiskInput) -> RiskAssessment:
    """Score a borrower across all risk dimensions (Property 8).

    Returns a RiskAssessment with:
    - Weighted composite score (0–1000)
    - Category (LOW/MEDIUM/HIGH/VERY_HIGH)
    - Per-factor breakdown and explanations
    """
    factors = [
        _score_income_volatility(inp),
        _score_debt_exposure(inp),
        _score_repayment_history(inp),
        _score_seasonal_risk(inp),
        _score_weather_risk(inp),
        _score_market_risk(inp),
        _score_demographic(inp),
        _score_crop_diversification(inp),
    ]

    # Weighted composite: each factor is 0–100, scale to 0–1000
    weighted = sum(f.score * f.weight for f in factors)
    risk_score = round(weighted * 10)  # 0–1000

    # Categorise
    if risk_score < 250:
        category = RiskCategory.LOW
    elif risk_score < 500:
        category = RiskCategory.MEDIUM
    elif risk_score < 750:
        category = RiskCategory.HIGH
    else:
        category = RiskCategory.VERY_HIGH

    # Confidence: higher if we have more data points
    data_richness = sum(1 for f in factors if f.score > 0) / len(factors)
    confidence = round(min(0.95, 0.5 + data_richness * 0.4), 2)

    # Build explanation
    top_factors = sorted(factors, key=lambda f: f.score * f.weight, reverse=True)[:3]
    key_factor_strs = [f"{f.factor_type.value}: {f.description}" for f in top_factors]

    recommendations = _generate_recommendations(factors, category)

    explanation = RiskExplanation(
        summary=f"Risk score {risk_score}/1000 ({category.value}). "
                f"Primary drivers: {', '.join(f.factor_type.value for f in top_factors[:2])}.",
        key_factors=key_factor_strs,
        recommendations=recommendations,
        confidence_note=f"Confidence {confidence:.0%} based on {sum(1 for f in factors if f.score > 0)}/{len(factors)} active factors.",
    )

    now = datetime.now(UTC)
    from datetime import timedelta
    valid_days = 30 if category in (RiskCategory.LOW, RiskCategory.MEDIUM) else 7

    return RiskAssessment(
        assessment_id=generate_id(),
        profile_id=inp.profile_id,
        risk_score=risk_score,
        risk_category=category,
        confidence_level=confidence,
        factors=factors,
        explanation=explanation,
        valid_until=now + timedelta(days=valid_days),
        created_at=now,
        updated_at=now,
    )


def _generate_recommendations(
    factors: list[RiskFactor], category: RiskCategory,
) -> list[str]:
    """Generate actionable recommendations based on risk factors."""
    recs: list[str] = []

    factor_map = {f.factor_type: f for f in factors}

    debt = factor_map.get(RiskFactorType.DEBT_EXPOSURE)
    if debt and debt.score > 60:
        recs.append("Consider consolidating multiple loans to reduce monthly obligations.")

    income = factor_map.get(RiskFactorType.INCOME_VOLATILITY)
    if income and income.score > 50:
        recs.append("Diversify income sources to reduce cash-flow volatility.")

    repay = factor_map.get(RiskFactorType.REPAYMENT_HISTORY)
    if repay and repay.score > 40:
        recs.append("Prioritize timely repayments to improve credit standing.")

    crop = factor_map.get(RiskFactorType.CROP_DIVERSIFICATION)
    if crop and crop.score > 60:
        recs.append("Diversify crops across seasons (Kharif/Rabi/Zaid) to spread risk.")

    seasonal = factor_map.get(RiskFactorType.SEASONAL_RISK)
    if seasonal and seasonal.score > 50:
        recs.append("Invest in irrigation to reduce dependency on monsoon patterns.")

    if not recs:
        recs.append("Risk profile is healthy. Maintain current financial practices.")

    return recs
