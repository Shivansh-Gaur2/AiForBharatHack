"""Cash Flow Service domain entities — pure Python, zero infrastructure imports.

Design doc ref: §3 Cash Flow Service
Properties validated: P6 (Cash Flow Integration), P7 (Timing Alignment)
Requirements: Req 3 (Cash Flow Prediction and Alignment)

Models seasonal income/expense patterns for rural borrowers, generates
monthly cash-flow projections, computes repayment capacity, and determines
optimal credit timing aligned with income peaks.

Uses the SeasonalRegressionCashFlowModel (seasonal-regression-v2) from the
shared AI layer for higher-quality projections; falls back to seasonal-avg-v1.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from services.shared.models import ProfileId, Season, generate_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CashFlowCategory(StrEnum):
    CROP_INCOME = "CROP_INCOME"
    LIVESTOCK_INCOME = "LIVESTOCK_INCOME"
    LABOUR_INCOME = "LABOUR_INCOME"
    REMITTANCE = "REMITTANCE"
    GOVERNMENT_SUBSIDY = "GOVERNMENT_SUBSIDY"
    OTHER_INCOME = "OTHER_INCOME"
    SEED_FERTILIZER = "SEED_FERTILIZER"
    LABOUR_EXPENSE = "LABOUR_EXPENSE"
    EQUIPMENT = "EQUIPMENT"
    HOUSEHOLD = "HOUSEHOLD"
    EDUCATION = "EDUCATION"
    HEALTHCARE = "HEALTHCARE"
    LOAN_REPAYMENT = "LOAN_REPAYMENT"
    OTHER_EXPENSE = "OTHER_EXPENSE"


class FlowDirection(StrEnum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


class ForecastConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MonthlyProjection:
    """Projected cash flow for a single month."""
    month: int                   # 1–12
    year: int
    projected_inflow: float
    projected_outflow: float
    net_cash_flow: float         # inflow - outflow
    confidence: ForecastConfidence
    notes: str = ""

    @property
    def surplus_ratio(self) -> float:
        """Fraction of inflow that is surplus (0–1+)."""
        if self.projected_inflow <= 0:
            return 0.0
        return self.net_cash_flow / self.projected_inflow


@dataclass(frozen=True)
class SeasonalPattern:
    """Observed seasonal cash-flow pattern for a category."""
    category: CashFlowCategory
    direction: FlowDirection
    season: Season
    months: list[int]                    # active months (1–12)
    average_monthly_amount: float
    peak_month: int                      # month with highest amount
    variability_cv: float                # coefficient of variation


@dataclass(frozen=True)
class CashFlowRecord:
    """A single historical cash-flow data point."""
    record_id: str
    profile_id: ProfileId
    category: CashFlowCategory
    direction: FlowDirection
    amount: float
    month: int
    year: int
    season: Season | None = None
    notes: str = ""
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class UncertaintyBand:
    """Confidence interval around a projection."""
    month: int
    year: int
    lower_bound: float            # 10th percentile
    expected: float               # 50th percentile (median)
    upper_bound: float            # 90th percentile


@dataclass(frozen=True)
class ForecastAssumption:
    """An assumption underpinning the forecast."""
    factor: str
    description: str
    impact: str                   # "positive", "negative", "neutral"


@dataclass(frozen=True)
class TimingWindow:
    """A recommended credit-timing window."""
    start_month: int
    start_year: int
    end_month: int
    end_year: int
    suitability_score: float       # 0–100  (higher = better time to borrow)
    reason: str


@dataclass(frozen=True)
class RepaymentCapacity:
    """Computed repayment capacity for a borrower (Req 3.4)."""
    profile_id: ProfileId
    monthly_surplus_avg: float           # average net inflow
    monthly_surplus_min: float           # worst-month surplus
    max_affordable_emi: float            # 60% of min surplus
    recommended_emi: float               # 40% of avg surplus
    emergency_reserve: float             # 3-month household expense buffer
    annual_repayment_capacity: float     # 12 × recommended EMI
    debt_service_coverage_ratio: float   # avg surplus / existing obligations
    computed_at: datetime


# ---------------------------------------------------------------------------
# Cash Flow Forecast Aggregate
# ---------------------------------------------------------------------------
@dataclass
class CashFlowForecast:
    """Complete cash-flow forecast for a borrower (Aggregate Root)."""
    forecast_id: str
    profile_id: ProfileId
    forecast_period_start_month: int
    forecast_period_start_year: int
    forecast_period_end_month: int
    forecast_period_end_year: int
    monthly_projections: list[MonthlyProjection]
    seasonal_patterns: list[SeasonalPattern]
    uncertainty_bands: list[UncertaintyBand]
    assumptions: list[ForecastAssumption]
    repayment_capacity: RepaymentCapacity
    timing_windows: list[TimingWindow]
    model_version: str = "seasonal-avg-v1"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_best_timing_window(self) -> TimingWindow | None:
        """Return the window with highest suitability score."""
        if not self.timing_windows:
            return None
        return max(self.timing_windows, key=lambda w: w.suitability_score)

    def get_worst_month(self) -> MonthlyProjection | None:
        """Month with lowest net cash flow."""
        if not self.monthly_projections:
            return None
        return min(self.monthly_projections, key=lambda p: p.net_cash_flow)

    def get_total_projected_inflow(self) -> float:
        return sum(p.projected_inflow for p in self.monthly_projections)

    def get_total_projected_outflow(self) -> float:
        return sum(p.projected_outflow for p in self.monthly_projections)


# ---------------------------------------------------------------------------
# Seasonal Analysis Engine (pure domain logic)
# ---------------------------------------------------------------------------
def analyse_seasonal_patterns(
    records: list[CashFlowRecord],
) -> list[SeasonalPattern]:
    """Discover seasonal patterns from historical cash-flow records.

    Groups records by (category, direction), computes monthly averages,
    identifies peak months, and measures variability.
    """
    # Group by (category, direction)
    groups: dict[tuple[CashFlowCategory, FlowDirection], list[CashFlowRecord]] = {}
    for r in records:
        key = (r.category, r.direction)
        groups.setdefault(key, []).append(r)

    patterns: list[SeasonalPattern] = []
    for (cat, direction), cat_records in groups.items():
        # Monthly aggregation
        month_sums: dict[int, list[float]] = {}
        for r in cat_records:
            month_sums.setdefault(r.month, []).append(r.amount)

        monthly_avgs = {
            m: statistics.mean(amounts) for m, amounts in month_sums.items()
        }
        if not monthly_avgs:
            continue

        active_months = sorted(monthly_avgs.keys())
        peak_month = max(monthly_avgs, key=lambda m: monthly_avgs[m])
        overall_avg = statistics.mean(monthly_avgs.values())

        # CV across months
        if len(monthly_avgs) >= 2 and overall_avg > 0:
            cv = statistics.stdev(monthly_avgs.values()) / overall_avg
        else:
            cv = 0.0

        # Determine season from peak month
        season = _month_to_season(peak_month)

        patterns.append(SeasonalPattern(
            category=cat,
            direction=direction,
            season=season,
            months=active_months,
            average_monthly_amount=round(overall_avg, 2),
            peak_month=peak_month,
            variability_cv=round(cv, 4),
        ))

    return patterns


def _month_to_season(month: int) -> Season:
    """Map a calendar month to the dominant agricultural season."""
    if month in (6, 7, 8, 9, 10):      # Jun–Oct
        return Season.KHARIF
    elif month in (11, 12, 1, 2, 3):    # Nov–Mar
        return Season.RABI
    else:                                # Apr–May
        return Season.ZAID


# ---------------------------------------------------------------------------
# Cash Flow Projection Engine (Req 3.1, 3.2)
# ---------------------------------------------------------------------------
def generate_projections(
    patterns: list[SeasonalPattern],
    horizon_months: int,
    start_month: int,
    start_year: int,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
) -> list[MonthlyProjection]:
    """Generate monthly cash-flow projections from seasonal patterns.

    Adjustments from external data (weather, market) scale the projections.
    """
    projections: list[MonthlyProjection] = []

    for i in range(horizon_months):
        m = ((start_month - 1 + i) % 12) + 1
        y = start_year + (start_month - 1 + i) // 12

        inflow = 0.0
        outflow = 0.0

        for pat in patterns:
            if m not in pat.months:
                continue
            adj_amount = pat.average_monthly_amount
            if pat.direction == FlowDirection.INFLOW:
                # Adjust for weather/market impacts
                adj_amount *= weather_adjustment * market_adjustment
                inflow += adj_amount
            else:
                outflow += adj_amount

        net = inflow - outflow

        # Confidence based on data quality
        if inflow > 0 and outflow > 0:
            conf = ForecastConfidence.HIGH
        elif inflow > 0 or outflow > 0:
            conf = ForecastConfidence.MEDIUM
        else:
            conf = ForecastConfidence.LOW

        projections.append(MonthlyProjection(
            month=m,
            year=y,
            projected_inflow=round(inflow, 2),
            projected_outflow=round(outflow, 2),
            net_cash_flow=round(net, 2),
            confidence=conf,
        ))

    return projections


# ---------------------------------------------------------------------------
# Uncertainty Estimation
# ---------------------------------------------------------------------------
def compute_uncertainty_bands(
    projections: list[MonthlyProjection],
    patterns: list[SeasonalPattern],
) -> list[UncertaintyBand]:
    """Compute P10/P50/P90 uncertainty bands for each projected month."""
    # Aggregate CV across all patterns for a rough volatility estimate
    cvs = [p.variability_cv for p in patterns if p.variability_cv > 0]
    avg_cv = statistics.mean(cvs) if cvs else 0.15  # default 15% uncertainty

    bands: list[UncertaintyBand] = []
    for proj in projections:
        expected = proj.net_cash_flow
        sigma = abs(expected) * avg_cv if expected != 0 else 0
        # z-scores: 10th percentile ≈ -1.28, 90th ≈ +1.28
        lower = expected - 1.28 * sigma
        upper = expected + 1.28 * sigma
        bands.append(UncertaintyBand(
            month=proj.month,
            year=proj.year,
            lower_bound=round(lower, 2),
            expected=round(expected, 2),
            upper_bound=round(upper, 2),
        ))

    return bands


# ---------------------------------------------------------------------------
# Repayment Capacity Calculator (Req 3.4, 3.5)
# ---------------------------------------------------------------------------
def compute_repayment_capacity(
    profile_id: ProfileId,
    projections: list[MonthlyProjection],
    existing_monthly_obligations: float = 0.0,
    household_monthly_expense: float = 0.0,
) -> RepaymentCapacity:
    """Compute how much a borrower can afford to repay per month.

    Accounts for emergency reserves (Req 3.5): 3 months of household expenses.
    """
    surpluses = [p.net_cash_flow for p in projections]

    if not surpluses:
        return RepaymentCapacity(
            profile_id=profile_id,
            monthly_surplus_avg=0.0,
            monthly_surplus_min=0.0,
            max_affordable_emi=0.0,
            recommended_emi=0.0,
            emergency_reserve=household_monthly_expense * 3,
            annual_repayment_capacity=0.0,
            debt_service_coverage_ratio=0.0,
            computed_at=datetime.now(UTC),
        )

    avg_surplus = statistics.mean(surpluses)
    min_surplus = min(surpluses)

    # Max EMI: 60% of worst-month surplus (conservative)
    max_emi = max(0.0, min_surplus * 0.60)
    # Recommended EMI: 40% of average surplus
    rec_emi = max(0.0, avg_surplus * 0.40)
    # Emergency reserve: 3 months of household expenses
    emergency = household_monthly_expense * 3

    # DSCR: how well surplus covers existing + new obligations
    total_obligations = existing_monthly_obligations
    dscr = avg_surplus / total_obligations if total_obligations > 0 else 99.0

    return RepaymentCapacity(
        profile_id=profile_id,
        monthly_surplus_avg=round(avg_surplus, 2),
        monthly_surplus_min=round(min_surplus, 2),
        max_affordable_emi=round(max_emi, 2),
        recommended_emi=round(rec_emi, 2),
        emergency_reserve=round(emergency, 2),
        annual_repayment_capacity=round(rec_emi * 12, 2),
        debt_service_coverage_ratio=round(min(dscr, 99.0), 2),
        computed_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Credit Timing Alignment (Req 3.3, Property 7)
# ---------------------------------------------------------------------------
def compute_timing_windows(
    projections: list[MonthlyProjection],
    loan_tenure_months: int = 12,
) -> list[TimingWindow]:
    """Find optimal windows to take a loan, aligned with income peaks.

    For each possible start month, scores based on:
    - Average net cash flow during the repayment period
    - Whether disbursement aligns with an income peak
    - Minimum monthly surplus during the tenure
    """
    if not projections or loan_tenure_months <= 0:
        return []

    n = len(projections)
    windows: list[TimingWindow] = []

    # Sliding window over the projection horizon
    max_start = n - loan_tenure_months + 1
    if max_start <= 0:
        # Horizon too short for the tenure — use entire horizon
        avg_net = statistics.mean(p.net_cash_flow for p in projections)
        min_net = min(p.net_cash_flow for p in projections)
        score = _timing_score(avg_net, min_net, projections[0].projected_inflow)
        windows.append(TimingWindow(
            start_month=projections[0].month,
            start_year=projections[0].year,
            end_month=projections[-1].month,
            end_year=projections[-1].year,
            suitability_score=round(score, 1),
            reason="Full forecast horizon considered.",
        ))
        return windows

    for start_idx in range(max_start):
        window_projs = projections[start_idx : start_idx + loan_tenure_months]
        avg_net = statistics.mean(p.net_cash_flow for p in window_projs)
        min_net = min(p.net_cash_flow for p in window_projs)
        start_inflow = window_projs[0].projected_inflow

        score = _timing_score(avg_net, min_net, start_inflow)
        first = window_projs[0]
        last = window_projs[-1]

        # Reason
        if score >= 70:
            reason = "Strong alignment with income peaks; healthy surplus throughout."
        elif score >= 40:
            reason = "Moderate alignment; some months may be tight."
        else:
            reason = "Weak alignment; consider deferring if possible."

        windows.append(TimingWindow(
            start_month=first.month,
            start_year=first.year,
            end_month=last.month,
            end_year=last.year,
            suitability_score=round(score, 1),
            reason=reason,
        ))

    return windows


def _timing_score(avg_net: float, min_net: float, start_inflow: float) -> float:
    """Composite suitability score 0–100."""
    # Component 1: average surplus normalised (0–40)
    surplus_component = 0.0 if avg_net <= 0 else min(40.0, math.log1p(avg_net / 1000) * 15)

    # Component 2: worst-month safety (0–30)
    if min_net >= 0:
        safety_component = min(30.0, 15 + math.log1p(min_net / 500) * 10)
    else:
        safety_component = max(0.0, 15 + min_net / 1000 * 15)

    # Component 3: disbursement-month income boost (0–30)
    income_component = min(30.0, math.log1p(start_inflow / 2000) * 12) if start_inflow > 0 else 0.0

    return min(100.0, surplus_component + safety_component + income_component)


# ---------------------------------------------------------------------------
# AI-enhanced projection engine  (seasonal-regression-v2)
# ---------------------------------------------------------------------------
def _try_ai_projections(
    records: list[CashFlowRecord],
    horizon_months: int,
    start_month: int,
    start_year: int,
    weather_adjustment: float,
    market_adjustment: float,
) -> tuple[list[MonthlyProjection], str] | None:
    """Try the SeasonalRegressionCashFlowModel; return (projections, version) or None."""
    try:
        from services.shared.ai import get_cashflow_model, engineer_cashflow_features

        model = get_cashflow_model()

        # Build monthly history from records
        month_flows: dict[tuple[int, int], dict[str, float]] = {}
        for r in records:
            key = (r.month, r.year)
            entry = month_flows.setdefault(key, {"inflow": 0.0, "outflow": 0.0})
            if r.direction == FlowDirection.INFLOW:
                entry["inflow"] += r.amount
            else:
                entry["outflow"] += r.amount

        # Sort chronologically
        sorted_keys = sorted(month_flows.keys(), key=lambda k: (k[1], k[0]))
        monthly_history = [
            {"month": m, "year": y, "inflow": month_flows[(m, y)]["inflow"],
             "outflow": month_flows[(m, y)]["outflow"]}
            for m, y in sorted_keys
        ]

        if len(monthly_history) < 3:
            return None  # Not enough data for AI model

        external_factors = {
            "weather_risk": max(0.0, 1.0 - weather_adjustment),
            "market_price_change": market_adjustment - 1.0,
        }

        result = model.predict_cashflow(
            monthly_history=monthly_history,
            horizon_months=horizon_months,
            external_factors=external_factors,
        )

        projections: list[MonthlyProjection] = []
        for mp in result.monthly_predictions:
            conf = ForecastConfidence.HIGH
            if mp.confidence < 0.5:
                conf = ForecastConfidence.LOW
            elif mp.confidence < 0.75:
                conf = ForecastConfidence.MEDIUM

            projections.append(MonthlyProjection(
                month=mp.month,
                year=mp.year,
                projected_inflow=round(mp.predicted_inflow, 2),
                projected_outflow=round(mp.predicted_outflow, 2),
                net_cash_flow=round(mp.predicted_inflow - mp.predicted_outflow, 2),
                confidence=conf,
                notes=f"AI model (confidence={mp.confidence:.0%})",
            ))

        return projections, result.model_version

    except Exception:
        logger.warning(
            "AI cashflow model unavailable, falling back to seasonal-avg-v1",
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Forecast Factory
# ---------------------------------------------------------------------------
def build_forecast(
    profile_id: ProfileId,
    records: list[CashFlowRecord],
    horizon_months: int = 12,
    start_month: int | None = None,
    start_year: int | None = None,
    existing_monthly_obligations: float = 0.0,
    household_monthly_expense: float = 0.0,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
    loan_tenure_months: int = 12,
) -> CashFlowForecast:
    """Build a complete cash-flow forecast from historical records.

    This is the main entry point for generating forecasts. It:
    1. Analyses seasonal patterns from historical records
    2. Generates monthly projections
    3. Computes uncertainty bands
    4. Computes repayment capacity (Req 3.4, 3.5)
    5. Identifies optimal credit-timing windows (Req 3.3)
    """
    now = datetime.now(UTC)
    if start_month is None:
        start_month = now.month
    if start_year is None:
        start_year = now.year

    # 1) Seasonal patterns (always computed — used for uncertainty & comparison)
    patterns = analyse_seasonal_patterns(records)

    # 2) Monthly projections — try AI model first, fall back to seasonal avg
    model_version = "seasonal-avg-v1"
    ai_result = _try_ai_projections(
        records, horizon_months, start_month, start_year,
        weather_adjustment, market_adjustment,
    )
    if ai_result is not None:
        projections, model_version = ai_result
    else:
        projections = generate_projections(
            patterns, horizon_months, start_month, start_year,
            weather_adjustment=weather_adjustment,
            market_adjustment=market_adjustment,
        )

    # 3) Uncertainty bands
    bands = compute_uncertainty_bands(projections, patterns)

    # 4) Repayment capacity
    capacity = compute_repayment_capacity(
        profile_id, projections,
        existing_monthly_obligations=existing_monthly_obligations,
        household_monthly_expense=household_monthly_expense,
    )

    # 5) Timing windows
    timing = compute_timing_windows(projections, loan_tenure_months)

    # Build assumptions
    assumptions: list[ForecastAssumption] = []
    if weather_adjustment != 1.0:
        impact = "negative" if weather_adjustment < 1.0 else "positive"
        assumptions.append(ForecastAssumption(
            factor="Weather",
            description=f"Weather adjustment factor: {weather_adjustment:.2f}",
            impact=impact,
        ))
    if market_adjustment != 1.0:
        impact = "negative" if market_adjustment < 1.0 else "positive"
        assumptions.append(ForecastAssumption(
            factor="Market",
            description=f"Market price adjustment factor: {market_adjustment:.2f}",
            impact=impact,
        ))
    if not assumptions:
        assumptions.append(ForecastAssumption(
            factor="Baseline",
            description="No external adjustments applied; using historical averages.",
            impact="neutral",
        ))

    end_month = ((start_month - 1 + horizon_months - 1) % 12) + 1
    end_year = start_year + (start_month - 1 + horizon_months - 1) // 12

    return CashFlowForecast(
        forecast_id=generate_id(),
        profile_id=profile_id,
        forecast_period_start_month=start_month,
        forecast_period_start_year=start_year,
        forecast_period_end_month=end_month,
        forecast_period_end_year=end_year,
        monthly_projections=projections,
        seasonal_patterns=patterns,
        uncertainty_bands=bands,
        assumptions=assumptions,
        repayment_capacity=capacity,
        timing_windows=timing,
        model_version=model_version,
        created_at=now,
        updated_at=now,
    )
