"""Early Warning & Scenario Simulation domain entities — pure Python, zero infrastructure imports.

Design doc ref: §5 Early Warning System, §6 Scenario Simulation Engine
Properties validated: P10 (Alert Generation & Escalation), P11 (Scenario Simulation Completeness)

This module defines:
 - Alert lifecycle: generation, escalation, acknowledgement
 - Income deviation monitoring
 - Repayment stress detection
 - Scenario simulation (weather, market, income shocks)
 - Risk-adjusted recommendations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from services.shared.models import (
    AlertId,
    AlertSeverity,
    AlertType,
    ProfileId,
    RiskCategory,
    generate_id,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class AlertStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"


class ScenarioType(StrEnum):
    INCOME_SHOCK = "INCOME_SHOCK"
    WEATHER_IMPACT = "WEATHER_IMPACT"
    MARKET_VOLATILITY = "MARKET_VOLATILITY"
    COMBINED = "COMBINED"


class RecommendationPriority(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class IncomeDeviation:
    """Measures deviation of actual income from expected/forecast."""
    month: int
    year: int
    expected_income: float
    actual_income: float
    deviation_pct: float           # (actual - expected) / expected * 100
    is_significant: bool           # |deviation| > threshold (default 20%)


@dataclass(frozen=True)
class RepaymentStressIndicator:
    """Signals of repayment difficulty for a borrower."""
    dti_ratio: float               # debt-to-income ratio
    missed_payments: int           # count in recent window
    days_overdue_avg: float        # average days overdue on recent payments
    declining_surplus: bool        # net cash flow trending down
    stress_score: float            # composite 0–100 (higher = more stress)


@dataclass(frozen=True)
class ActionableRecommendation:
    """A concrete, actionable recommendation attached to an alert."""
    action: str                    # e.g., "Reduce non-essential spending by ₹2,000/month"
    rationale: str                 # why this helps
    priority: RecommendationPriority
    estimated_impact: str          # e.g., "Improves repayment margin by 15%"


@dataclass(frozen=True)
class RiskFactorSnapshot:
    """A snapshot of a risk factor that contributed to an alert."""
    factor_name: str               # e.g., "DEBT_EXPOSURE"
    current_value: float
    threshold: float
    severity_contribution: str     # how much this factor contributes


# ---------------------------------------------------------------------------
# Alert Aggregate
# ---------------------------------------------------------------------------
@dataclass
class Alert:
    """Early warning alert — aggregate root.

    Lifecycle: ACTIVE → ACKNOWLEDGED → RESOLVED
    Severity can be escalated (INFO → WARNING → CRITICAL) but never downgraded.
    """
    alert_id: AlertId
    profile_id: ProfileId
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    risk_factors: list[RiskFactorSnapshot]
    recommendations: list[ActionableRecommendation]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def escalate(self, new_severity: AlertSeverity, reason: str) -> None:
        """Escalate severity — only upwards (INFO < WARNING < CRITICAL)."""
        severity_order = {AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1, AlertSeverity.CRITICAL: 2}
        if severity_order[new_severity] <= severity_order[self.severity]:
            return  # cannot downgrade or same level
        self.severity = new_severity
        self.description += f"\n[Escalated to {new_severity}] {reason}"
        self.updated_at = datetime.now(UTC)

    def acknowledge(self) -> None:
        """Mark alert as acknowledged by the borrower/stakeholder."""
        if self.status == AlertStatus.ACTIVE:
            self.status = AlertStatus.ACKNOWLEDGED
            self.acknowledged_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    def resolve(self) -> None:
        """Mark alert as resolved — risk has been mitigated."""
        if self.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED):
            self.status = AlertStatus.RESOLVED
            self.resolved_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    def is_active(self) -> bool:
        return self.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)

    @staticmethod
    def create(
        profile_id: ProfileId,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        description: str,
        risk_factors: list[RiskFactorSnapshot] | None = None,
        recommendations: list[ActionableRecommendation] | None = None,
    ) -> Alert:
        now = datetime.now(UTC)
        return Alert(
            alert_id=generate_id(),
            profile_id=profile_id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            risk_factors=risk_factors or [],
            recommendations=recommendations or [],
            created_at=now,
            updated_at=now,
        )


# ---------------------------------------------------------------------------
# Scenario Simulation Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioParameters:
    """Input parameters for a what-if scenario simulation."""
    scenario_type: ScenarioType
    name: str                      # human-readable label
    description: str = ""
    # Income shock parameters
    income_reduction_pct: float = 0.0       # 0–100, how much income drops
    # Weather impact parameters
    weather_adjustment: float = 1.0         # multiplier (0.3=severe drought, 1.0=normal)
    # Market volatility parameters
    market_price_change_pct: float = 0.0    # -50 to +50, crop price change
    # Duration
    duration_months: int = 6                # how long the shock lasts
    # Existing obligations (for capacity recalc)
    existing_monthly_obligations: float = 0.0
    household_monthly_expense: float = 5000.0


@dataclass(frozen=True)
class CapacityImpact:
    """How a scenario impacts repayment capacity."""
    original_recommended_emi: float
    stressed_recommended_emi: float
    original_max_emi: float
    stressed_max_emi: float
    original_dscr: float           # debt service coverage ratio
    stressed_dscr: float
    emi_reduction_pct: float       # how much EMI capacity drops
    can_still_repay: bool          # can still meet obligations?


@dataclass(frozen=True)
class ScenarioProjection:
    """Monthly projection under a scenario."""
    month: int
    year: int
    baseline_inflow: float
    stressed_inflow: float
    baseline_outflow: float
    stressed_outflow: float
    baseline_net: float
    stressed_net: float


@dataclass(frozen=True)
class ScenarioRecommendation:
    """Risk-adjusted recommendation from scenario analysis."""
    recommendation: str
    risk_level: str                # "LOW", "MEDIUM", "HIGH", "VERY_HIGH"
    confidence: str                # "HIGH", "MEDIUM", "LOW"
    rationale: str


# ---------------------------------------------------------------------------
# Simulation Result Aggregate
# ---------------------------------------------------------------------------
@dataclass
class SimulationResult:
    """Complete result of a scenario simulation — aggregate root."""
    simulation_id: str
    profile_id: ProfileId
    scenario: ScenarioParameters
    projections: list[ScenarioProjection]
    capacity_impact: CapacityImpact
    recommendations: list[ScenarioRecommendation]
    overall_risk_level: str        # assessed risk under this scenario
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_worst_month(self) -> ScenarioProjection | None:
        """Month with the largest negative net cash flow under stress."""
        if not self.projections:
            return None
        return min(self.projections, key=lambda p: p.stressed_net)

    def get_total_income_loss(self) -> float:
        """Total income loss compared to baseline."""
        return sum(p.baseline_inflow - p.stressed_inflow for p in self.projections)

    def months_in_deficit(self) -> int:
        """Number of months with negative net cash flow under stress."""
        return sum(1 for p in self.projections if p.stressed_net < 0)


# ===========================================================================
# Pure Domain Functions — Early Warning Logic
# ===========================================================================

def compute_income_deviations(
    expected_incomes: list[tuple[int, int, float]],   # (month, year, expected)
    actual_incomes: list[tuple[int, int, float]],     # (month, year, actual)
    threshold_pct: float = 20.0,
) -> list[IncomeDeviation]:
    """Compare expected vs actual income to detect significant deviations.

    Req 5.2: monitor income deviations from expected patterns.
    """
    actual_map = {(m, y): amt for m, y, amt in actual_incomes}
    deviations: list[IncomeDeviation] = []

    for month, year, expected in expected_incomes:
        actual = actual_map.get((month, year), 0.0)
        if expected > 0:
            dev_pct = (actual - expected) / expected * 100
        else:
            dev_pct = 0.0 if actual == 0 else 100.0

        deviations.append(IncomeDeviation(
            month=month,
            year=year,
            expected_income=expected,
            actual_income=actual,
            deviation_pct=round(dev_pct, 1),
            is_significant=abs(dev_pct) >= threshold_pct,
        ))

    return deviations


def compute_repayment_stress(
    dti_ratio: float,
    missed_payments: int,
    days_overdue_avg: float,
    recent_surplus_trend: list[float],  # last N months' net cash flow
) -> RepaymentStressIndicator:
    """Compute a composite repayment stress score (Req 5.1).

    Components:
    - DTI severity (0–30): DTI > 0.4 is concerning, > 0.6 is critical
    - Missed payment impact (0–30): each miss adds severity
    - Overdue days impact (0–20): longer overdue = higher stress
    - Cash flow trend (0–20): declining surplus trend
    """
    # DTI component (0–30)
    dti_component = min(30.0, dti_ratio * 50) if dti_ratio > 0 else 0.0

    # Missed payments (0–30)
    missed_component = min(30.0, missed_payments * 10.0)

    # Days overdue (0–20)
    overdue_component = min(20.0, days_overdue_avg / 3.0)

    # Cash flow trend (0–20)
    declining = False
    if len(recent_surplus_trend) >= 3:
        # Check if the trend is downward (linear regression slope < 0)
        n = len(recent_surplus_trend)
        x_mean = (n - 1) / 2
        y_mean = sum(recent_surplus_trend) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent_surplus_trend))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator > 0 else 0.0
        declining = slope < 0
        # Normalize slope impact
        trend_component = min(20.0, max(0.0, -slope / 500 * 20)) if slope < 0 else 0.0
    else:
        trend_component = 0.0

    stress_score = min(100.0, dti_component + missed_component + overdue_component + trend_component)

    return RepaymentStressIndicator(
        dti_ratio=round(dti_ratio, 3),
        missed_payments=missed_payments,
        days_overdue_avg=round(days_overdue_avg, 1),
        declining_surplus=declining,
        stress_score=round(stress_score, 1),
    )


def determine_alert_severity(
    stress: RepaymentStressIndicator,
    deviations: list[IncomeDeviation],
    risk_category: RiskCategory | None = None,
) -> AlertSeverity:
    """Determine alert severity based on multi-factor alignment (Req 5.3).

    Escalation logic:
    - CRITICAL: stress > 60 AND multiple significant deviations AND high/very_high risk
    - WARNING: stress > 30 OR significant deviations detected OR high risk
    - INFO: any early indicators present
    """
    sig_devs = sum(1 for d in deviations if d.is_significant and d.deviation_pct < 0)
    high_risk = risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH)

    # Multi-factor alignment → CRITICAL
    if stress.stress_score > 60 and sig_devs >= 2 and high_risk:
        return AlertSeverity.CRITICAL
    if stress.stress_score > 70:
        return AlertSeverity.CRITICAL

    # Single-factor concerning → WARNING
    if stress.stress_score > 30 or sig_devs >= 2 or high_risk:
        return AlertSeverity.WARNING

    # Early indicators → INFO
    return AlertSeverity.INFO


def generate_recommendations(
    stress: RepaymentStressIndicator,
    deviations: list[IncomeDeviation],
    severity: AlertSeverity,
) -> list[ActionableRecommendation]:
    """Generate actionable recommendations based on the alert context (Req 5.4)."""
    recs: list[ActionableRecommendation] = []

    # DTI-based recommendations
    if stress.dti_ratio > 0.5:
        recs.append(ActionableRecommendation(
            action="Contact lender to discuss loan restructuring options",
            rationale=f"Debt-to-income ratio of {stress.dti_ratio:.0%} exceeds safe threshold of 50%",
            priority=RecommendationPriority.IMMEDIATE,
            estimated_impact="Could reduce monthly obligations by 20-30%",
        ))
    elif stress.dti_ratio > 0.3:
        recs.append(ActionableRecommendation(
            action="Avoid taking on additional debt until existing obligations reduce",
            rationale=f"Debt-to-income ratio of {stress.dti_ratio:.0%} is approaching unsafe levels",
            priority=RecommendationPriority.SHORT_TERM,
            estimated_impact="Prevents further financial strain",
        ))

    # Missed payment recommendations
    if stress.missed_payments > 0:
        recs.append(ActionableRecommendation(
            action="Prioritize upcoming loan repayment to avoid penalty charges",
            rationale=f"{stress.missed_payments} missed payment(s) detected — late fees compound quickly",
            priority=RecommendationPriority.IMMEDIATE,
            estimated_impact="Avoids additional 2-5% penalty charges",
        ))

    # Income deviation recommendations
    negative_devs = [d for d in deviations if d.is_significant and d.deviation_pct < 0]
    if negative_devs:
        avg_shortfall = abs(sum(d.deviation_pct for d in negative_devs) / len(negative_devs))
        recs.append(ActionableRecommendation(
            action="Explore alternative income sources to compensate for shortfall",
            rationale=f"Income is {avg_shortfall:.0f}% below expected — diversification can buffer shocks",
            priority=RecommendationPriority.SHORT_TERM,
            estimated_impact=f"Could offset {avg_shortfall/2:.0f}% of income gap",
        ))

    # Declining surplus
    if stress.declining_surplus:
        recs.append(ActionableRecommendation(
            action="Reduce non-essential household spending by ₹1,000-2,000/month",
            rationale="Net cash flow has been declining over recent months",
            priority=RecommendationPriority.SHORT_TERM,
            estimated_impact="Improves repayment buffer by ₹12,000-24,000/year",
        ))

    # Critical severity — emergency measures
    if severity == AlertSeverity.CRITICAL:
        recs.append(ActionableRecommendation(
            action="Contact local agricultural extension officer for emergency support schemes",
            rationale="Multiple risk factors indicate severe financial stress",
            priority=RecommendationPriority.IMMEDIATE,
            estimated_impact="Government schemes may provide ₹5,000-25,000 relief",
        ))

    # If no specific recs, provide general guidance
    if not recs:
        recs.append(ActionableRecommendation(
            action="Continue monitoring income and expenses closely",
            rationale="Early indicators suggest potential risk — awareness helps prevention",
            priority=RecommendationPriority.MEDIUM_TERM,
            estimated_impact="Proactive monitoring prevents 30-40% of defaults",
        ))

    return recs


def build_alert(
    profile_id: ProfileId,
    stress: RepaymentStressIndicator,
    deviations: list[IncomeDeviation],
    risk_category: RiskCategory | None = None,
    alert_type: AlertType | None = None,
) -> Alert:
    """Build an alert from stress/deviation analysis — orchestrator function.

    Determines severity, generates recommendations, creates the alert.
    """
    severity = determine_alert_severity(stress, deviations, risk_category)

    # Determine alert type if not provided
    if alert_type is None:
        sig_neg_devs = sum(1 for d in deviations if d.is_significant and d.deviation_pct < 0)
        if stress.stress_score > 40:
            alert_type = AlertType.REPAYMENT_STRESS
        elif sig_neg_devs > 0:
            alert_type = AlertType.INCOME_DEVIATION
        elif stress.dti_ratio > 0.5:
            alert_type = AlertType.OVER_INDEBTEDNESS
        else:
            alert_type = AlertType.REPAYMENT_STRESS

    # Build title and description
    title = _alert_title(alert_type, severity)
    description = _alert_description(stress, deviations, severity)

    # Build risk factor snapshots
    risk_factors = _build_risk_factor_snapshots(stress, deviations)

    # Generate recommendations
    recommendations = generate_recommendations(stress, deviations, severity)

    return Alert.create(
        profile_id=profile_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        description=description,
        risk_factors=risk_factors,
        recommendations=recommendations,
    )


def _alert_title(alert_type: AlertType, severity: AlertSeverity) -> str:
    titles = {
        AlertType.INCOME_DEVIATION: "Income Below Expected Levels",
        AlertType.REPAYMENT_STRESS: "Repayment Difficulty Detected",
        AlertType.OVER_INDEBTEDNESS: "Debt Levels Too High",
        AlertType.WEATHER_RISK: "Weather-Related Income Risk",
        AlertType.MARKET_RISK: "Market Price Impact on Income",
    }
    return titles.get(alert_type, "Financial Alert")


def _alert_description(
    stress: RepaymentStressIndicator,
    deviations: list[IncomeDeviation],
    severity: AlertSeverity,
) -> str:
    parts: list[str] = []
    if stress.stress_score > 30:
        parts.append(f"Repayment stress score: {stress.stress_score}/100.")

    sig_devs = [d for d in deviations if d.is_significant and d.deviation_pct < 0]
    if sig_devs:
        avg = abs(sum(d.deviation_pct for d in sig_devs) / len(sig_devs))
        parts.append(f"Income is {avg:.0f}% below expected in {len(sig_devs)} month(s).")

    if stress.missed_payments > 0:
        parts.append(f"{stress.missed_payments} missed payment(s) detected.")

    if stress.dti_ratio > 0.4:
        parts.append(f"Debt-to-income ratio: {stress.dti_ratio:.0%}.")

    if stress.declining_surplus:
        parts.append("Monthly surplus is declining.")

    return " ".join(parts) if parts else f"Routine financial monitoring check completed. No critical issues found."


def _build_risk_factor_snapshots(
    stress: RepaymentStressIndicator,
    deviations: list[IncomeDeviation],
) -> list[RiskFactorSnapshot]:
    factors: list[RiskFactorSnapshot] = []

    if stress.dti_ratio > 0.3:
        factors.append(RiskFactorSnapshot(
            factor_name="DEBT_EXPOSURE",
            current_value=stress.dti_ratio,
            threshold=0.4,
            severity_contribution="HIGH" if stress.dti_ratio > 0.5 else "MEDIUM",
        ))

    if stress.missed_payments > 0:
        factors.append(RiskFactorSnapshot(
            factor_name="REPAYMENT_HISTORY",
            current_value=float(stress.missed_payments),
            threshold=1.0,
            severity_contribution="HIGH" if stress.missed_payments >= 3 else "MEDIUM",
        ))

    sig_neg = [d for d in deviations if d.is_significant and d.deviation_pct < 0]
    if sig_neg:
        avg_dev = abs(sum(d.deviation_pct for d in sig_neg) / len(sig_neg))
        factors.append(RiskFactorSnapshot(
            factor_name="INCOME_VOLATILITY",
            current_value=avg_dev,
            threshold=20.0,
            severity_contribution="HIGH" if avg_dev > 40 else "MEDIUM",
        ))

    return factors


# ===========================================================================
# Pure Domain Functions — Scenario Simulation Logic
# ===========================================================================

def simulate_scenario(
    baseline_projections: list[tuple[int, int, float, float]],  # (month, year, inflow, outflow)
    params: ScenarioParameters,
    existing_monthly_obligations: float = 0.0,
    household_monthly_expense: float = 5000.0,
) -> SimulationResult:
    """Run a what-if scenario simulation against baseline cash flow projections.

    Req 6.1–6.5: Model income shocks, weather disruptions, market volatility,
    show impact on repayment capacity, provide risk-adjusted recs.
    """
    scenario_projections: list[ScenarioProjection] = []
    months_to_stress = min(params.duration_months, len(baseline_projections))

    for i, (month, year, base_inflow, base_outflow) in enumerate(baseline_projections):
        if i < months_to_stress:
            stressed_inflow = _apply_income_stress(
                base_inflow, params.income_reduction_pct,
                params.weather_adjustment, params.market_price_change_pct,
            )
        else:
            stressed_inflow = base_inflow  # shock has passed

        stressed_outflow = base_outflow  # expenses generally don't decrease

        scenario_projections.append(ScenarioProjection(
            month=month, year=year,
            baseline_inflow=round(base_inflow, 2),
            stressed_inflow=round(stressed_inflow, 2),
            baseline_outflow=round(base_outflow, 2),
            stressed_outflow=round(stressed_outflow, 2),
            baseline_net=round(base_inflow - base_outflow, 2),
            stressed_net=round(stressed_inflow - stressed_outflow, 2),
        ))

    # Compute capacity impact
    capacity = _compute_capacity_impact(
        scenario_projections, existing_monthly_obligations, household_monthly_expense,
    )

    # Determine overall risk level
    risk_level = _assess_scenario_risk(capacity, scenario_projections)

    # Generate risk-adjusted recommendations
    recommendations = _generate_scenario_recommendations(
        params, capacity, risk_level, scenario_projections,
    )

    return SimulationResult(
        simulation_id=generate_id(),
        profile_id="",  # caller sets this
        scenario=params,
        projections=scenario_projections,
        capacity_impact=capacity,
        recommendations=recommendations,
        overall_risk_level=risk_level,
    )


def _apply_income_stress(
    base_inflow: float,
    income_reduction_pct: float,
    weather_adjustment: float,
    market_price_change_pct: float,
) -> float:
    """Apply combined stress factors to income."""
    # Income shock factor
    income_factor = 1.0 - (income_reduction_pct / 100.0)
    # Weather factor is already a multiplier
    # Market factor
    market_factor = 1.0 + (market_price_change_pct / 100.0)

    stressed = base_inflow * income_factor * weather_adjustment * market_factor
    return max(0.0, stressed)


def _compute_capacity_impact(
    projections: list[ScenarioProjection],
    existing_obligations: float,
    household_expense: float,
) -> CapacityImpact:
    """Compute how the scenario impacts repayment capacity."""
    if not projections:
        return CapacityImpact(
            original_recommended_emi=0, stressed_recommended_emi=0,
            original_max_emi=0, stressed_max_emi=0,
            original_dscr=0, stressed_dscr=0,
            emi_reduction_pct=0, can_still_repay=False,
        )

    # Baseline capacity
    baseline_surpluses = [p.baseline_net for p in projections]
    baseline_avg = sum(baseline_surpluses) / len(baseline_surpluses)
    baseline_min = min(baseline_surpluses)

    # Stressed capacity
    stressed_surpluses = [p.stressed_net for p in projections]
    stressed_avg = sum(stressed_surpluses) / len(stressed_surpluses)
    stressed_min = min(stressed_surpluses)

    # EMI calculations (same formula as CashFlow service)
    orig_max_emi = max(0.0, baseline_min * 0.6 - existing_obligations)
    orig_rec_emi = max(0.0, baseline_avg * 0.4 - existing_obligations)

    stressed_max_emi = max(0.0, stressed_min * 0.6 - existing_obligations)
    stressed_rec_emi = max(0.0, stressed_avg * 0.4 - existing_obligations)

    # EMI reduction percentage
    emi_reduction = 0.0 if orig_rec_emi == 0 else (1 - stressed_rec_emi / orig_rec_emi) * 100

    # DSCR (coverage ratio relative to obligations)
    total_obligations = existing_obligations + household_expense
    orig_dscr = baseline_avg / total_obligations if total_obligations > 0 else 99.0
    stressed_dscr = stressed_avg / total_obligations if total_obligations > 0 else 99.0

    can_repay = stressed_min > existing_obligations

    return CapacityImpact(
        original_recommended_emi=round(orig_rec_emi, 2),
        stressed_recommended_emi=round(stressed_rec_emi, 2),
        original_max_emi=round(orig_max_emi, 2),
        stressed_max_emi=round(stressed_max_emi, 2),
        original_dscr=round(orig_dscr, 2),
        stressed_dscr=round(stressed_dscr, 2),
        emi_reduction_pct=round(emi_reduction, 1),
        can_still_repay=can_repay,
    )


def _assess_scenario_risk(
    capacity: CapacityImpact,
    projections: list[ScenarioProjection],
) -> str:
    """Assess overall risk level under a scenario."""
    deficit_months = sum(1 for p in projections if p.stressed_net < 0)
    deficit_ratio = deficit_months / len(projections) if projections else 0

    if not capacity.can_still_repay and deficit_ratio > 0.5:
        return RiskCategory.VERY_HIGH
    if capacity.emi_reduction_pct > 50 or deficit_ratio > 0.3:
        return RiskCategory.HIGH
    if capacity.emi_reduction_pct > 20 or deficit_ratio > 0.1:
        return RiskCategory.MEDIUM
    return RiskCategory.LOW


def _generate_scenario_recommendations(
    params: ScenarioParameters,
    capacity: CapacityImpact,
    risk_level: str,
    projections: list[ScenarioProjection],
) -> list[ScenarioRecommendation]:
    """Generate risk-adjusted recommendations from scenario analysis (Req 6.5)."""
    recs: list[ScenarioRecommendation] = []
    deficit_months = sum(1 for p in projections if p.stressed_net < 0)

    # Can't repay under scenario
    if not capacity.can_still_repay:
        recs.append(ScenarioRecommendation(
            recommendation="Consider reducing loan amount or extending tenure to lower EMI",
            risk_level=risk_level,
            confidence="HIGH",
            rationale=f"Under this scenario, repayment capacity drops by {capacity.emi_reduction_pct:.0f}% — "
                      f"current obligations may not be sustainable.",
        ))

    # Weather-specific
    if params.scenario_type in (ScenarioType.WEATHER_IMPACT, ScenarioType.COMBINED):
        if params.weather_adjustment < 0.7:
            recs.append(ScenarioRecommendation(
                recommendation="Invest in crop insurance (PMFBY) to protect against weather losses",
                risk_level=risk_level,
                confidence="HIGH",
                rationale="Severe weather could reduce income significantly — insurance provides a safety net.",
            ))
        else:
            recs.append(ScenarioRecommendation(
                recommendation="Monitor weather forecasts and prepare contingency irrigation plans",
                risk_level=risk_level,
                confidence="MEDIUM",
                rationale="Moderate weather impact expected — preparation reduces risk.",
            ))

    # Market-specific
    if params.scenario_type in (ScenarioType.MARKET_VOLATILITY, ScenarioType.COMBINED) and params.market_price_change_pct < -20:
            recs.append(ScenarioRecommendation(
                recommendation="Diversify crops or explore value-added processing to reduce price risk",
                risk_level=risk_level,
                confidence="MEDIUM",
                rationale=f"A {abs(params.market_price_change_pct):.0f}% price drop could significantly impact income.",
            ))

    # Income shock
    if params.scenario_type in (ScenarioType.INCOME_SHOCK, ScenarioType.COMBINED) and params.income_reduction_pct > 30:
            recs.append(ScenarioRecommendation(
                recommendation="Build an emergency fund of 3 months' expenses before taking this loan",
                risk_level=risk_level,
                confidence="HIGH",
                rationale=f"A {params.income_reduction_pct:.0f}% income drop would leave {deficit_months} month(s) in deficit.",
            ))

    # General timing recommendation
    if capacity.emi_reduction_pct > 25:
        recs.append(ScenarioRecommendation(
            recommendation="Time loan disbursement for post-harvest period when income is highest",
            risk_level=risk_level,
            confidence="MEDIUM",
            rationale="Aligning repayment with income peaks improves resilience to shocks.",
        ))

    # Optimistic scenario
    if risk_level == RiskCategory.LOW:
        recs.append(ScenarioRecommendation(
            recommendation="Current financial position can absorb this scenario — safe to proceed with planned borrowing",
            risk_level=risk_level,
            confidence="HIGH",
            rationale=f"EMI capacity reduces by only {capacity.emi_reduction_pct:.0f}% — well within tolerance.",
        ))

    return recs


def run_multi_scenario_comparison(
    baseline_projections: list[tuple[int, int, float, float]],
    scenarios: list[ScenarioParameters],
    existing_obligations: float = 0.0,
    household_expense: float = 5000.0,
) -> list[SimulationResult]:
    """Run multiple scenarios and return results for comparison (Req 6.1)."""
    results: list[SimulationResult] = []
    for params in scenarios:
        result = simulate_scenario(
            baseline_projections, params,
            existing_obligations, household_expense,
        )
        results.append(result)
    return results
