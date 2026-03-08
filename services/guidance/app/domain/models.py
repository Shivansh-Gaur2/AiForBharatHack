"""Domain models for the Guidance Service.

Pure business logic — zero framework or infrastructure imports.
Implements Req 7: Personalized Credit Guidance.

Uses the MultiObjectiveCreditOptimiser (moo-credit-v1) from the shared AI
layer to refine amount / tenure / timing recommendations.  Falls back to
rule-based logic when the optimiser is unavailable.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from services.shared.models import (
    AmountRange,
    GuidanceId,
    ProfileId,
    RiskCategory,
    Season,
    generate_id,
)

UTC = UTC
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LoanPurpose(StrEnum):
    """Common loan purposes for rural borrowers."""

    CROP_CULTIVATION = "CROP_CULTIVATION"
    LIVESTOCK_PURCHASE = "LIVESTOCK_PURCHASE"
    EQUIPMENT_PURCHASE = "EQUIPMENT_PURCHASE"
    LAND_IMPROVEMENT = "LAND_IMPROVEMENT"
    IRRIGATION = "IRRIGATION"
    WORKING_CAPITAL = "WORKING_CAPITAL"
    HOUSING = "HOUSING"
    EDUCATION = "EDUCATION"
    MEDICAL = "MEDICAL"
    DEBT_CONSOLIDATION = "DEBT_CONSOLIDATION"
    BUSINESS_EXPANSION = "BUSINESS_EXPANSION"
    OTHER = "OTHER"


class GuidanceStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class TimingSuitability(StrEnum):
    OPTIMAL = "OPTIMAL"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimingWindow:
    """Recommended time window for taking a loan."""

    start_month: int
    start_year: int
    end_month: int
    end_year: int
    suitability: TimingSuitability
    reason: str
    expected_surplus: float = 0.0


@dataclass(frozen=True)
class SuggestedTerms:
    """Recommended loan terms."""

    tenure_months: int
    interest_rate_max_pct: float
    emi_amount: float
    total_repayment: float
    source_recommendation: str  # e.g. "FORMAL", "SEMI_FORMAL"


@dataclass(frozen=True)
class RiskSummary:
    """Summary of risk assessment relevant to guidance."""

    risk_category: str
    risk_score: float
    dti_ratio: float
    repayment_capacity_pct: float  # % of income available for EMI
    key_risk_factors: list[str]


@dataclass(frozen=True)
class AlternativeOption:
    """An alternative credit approach."""

    option_type: str  # e.g. "SHG_LOAN", "CROP_INSURANCE", "GOVERNMENT_SCHEME"
    description: str
    estimated_amount: float
    advantages: list[str]
    disadvantages: list[str]


@dataclass(frozen=True)
class ReasoningStep:
    """One step in the explanation of guidance logic."""

    step_number: int
    factor: str
    observation: str
    impact: str  # e.g. "POSITIVE", "NEGATIVE", "NEUTRAL"


@dataclass(frozen=True)
class GuidanceExplanation:
    """Human-readable explanation of guidance reasoning (Req 7.5)."""

    summary: str
    reasoning_steps: list[ReasoningStep]
    confidence: ConfidenceLevel
    caveats: list[str]


@dataclass(frozen=True)
class MonthlyCapacity:
    """Repayment capacity for one month."""

    month: int
    year: int
    projected_inflow: float
    projected_outflow: float
    existing_obligations: float
    surplus: float  # inflow - outflow - obligations


@dataclass(frozen=True)
class SeasonalInsight:
    """Cash-flow insight for a season."""

    season: str
    avg_monthly_surplus: float
    min_surplus: float
    months_in_deficit: int
    suitability: TimingSuitability


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


@dataclass
class CreditGuidance:
    """Root aggregate representing personalized credit guidance (Req 7.1).

    This is the core output of the Guidance Service — everything the
    borrower needs to make an informed credit decision.
    """

    guidance_id: GuidanceId
    profile_id: ProfileId
    loan_purpose: LoanPurpose
    requested_amount: float | None  # what the borrower asked for (if any)

    # Recommendations
    recommended_amount: AmountRange
    optimal_timing: TimingWindow
    suggested_terms: SuggestedTerms
    risk_summary: RiskSummary
    alternative_options: list[AlternativeOption]
    explanation: GuidanceExplanation

    # Metadata
    status: GuidanceStatus = GuidanceStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def expire(self) -> None:
        self.status = GuidanceStatus.EXPIRED

    def supersede(self) -> None:
        self.status = GuidanceStatus.SUPERSEDED

    def is_active(self) -> bool:
        if self.status != GuidanceStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            self.status = GuidanceStatus.EXPIRED
            return False
        return True


# ---------------------------------------------------------------------------
# Pure Functions — Business Logic
# ---------------------------------------------------------------------------


def compute_monthly_capacities(
    projections: list[tuple[int, int, float, float]],
    existing_obligations: float,
) -> list[MonthlyCapacity]:
    """Compute per-month repayment capacity from cash-flow projections.

    Args:
        projections: [(month, year, inflow, outflow), ...]
        existing_obligations: monthly EMI for already-existing loans
    """
    result: list[MonthlyCapacity] = []
    for month, year, inflow, outflow in projections:
        surplus = inflow - outflow - existing_obligations
        result.append(MonthlyCapacity(
            month=month, year=year,
            projected_inflow=inflow,
            projected_outflow=outflow,
            existing_obligations=existing_obligations,
            surplus=surplus,
        ))
    return result


def compute_seasonal_insights(capacities: list[MonthlyCapacity]) -> list[SeasonalInsight]:
    """Derive seasonal suitability from monthly capacities."""
    season_map: dict[str, list[MonthlyCapacity]] = {}
    for cap in capacities:
        s = _month_to_season(cap.month)
        season_map.setdefault(s, []).append(cap)

    insights: list[SeasonalInsight] = []
    for season, months in season_map.items():
        surpluses = [m.surplus for m in months]
        avg = sum(surpluses) / len(surpluses) if surpluses else 0.0
        min_s = min(surpluses) if surpluses else 0.0
        deficit_count = sum(1 for s in surpluses if s < 0)
        suitability = _classify_timing_suitability(avg, min_s, deficit_count, len(months))
        insights.append(SeasonalInsight(
            season=season,
            avg_monthly_surplus=round(avg, 2),
            min_surplus=round(min_s, 2),
            months_in_deficit=deficit_count,
            suitability=suitability,
        ))
    return insights


def recommend_loan_amount(
    monthly_capacities: list[MonthlyCapacity],
    requested_amount: float | None,
    risk_category: str,
    tenure_months: int,
    interest_rate_annual: float = 9.0,
) -> AmountRange:
    """Recommend safe loan amount range based on repayment capacity (Req 7.3).

    Uses the sustainable EMI (fraction of average surplus) to compute
    how much principal the borrower can safely take on.
    """
    if not monthly_capacities:
        return AmountRange(min_amount=0.0, max_amount=0.0)

    surpluses = [c.surplus for c in monthly_capacities]
    avg_surplus = sum(surpluses) / len(surpluses)
    min_surplus = min(surpluses)

    # Risk-adjusted fraction of surplus usable for new EMI
    risk_factor = _risk_emi_fraction(risk_category)
    safe_emi = max(0.0, min_surplus * risk_factor)
    recommended_emi = max(0.0, avg_surplus * risk_factor)

    # Convert EMI to principal using present value of annuity
    min_principal = _emi_to_principal(safe_emi, interest_rate_annual, tenure_months)
    max_principal = _emi_to_principal(recommended_emi, interest_rate_annual, tenure_months)

    # If borrower requested a specific amount, clamp interpretation
    if requested_amount is not None:
        if requested_amount <= max_principal:
            min_principal = max(min_principal, requested_amount * 0.8)
            max_principal = max(max_principal, requested_amount * 1.0)
        else:
            # Requested too much — cap at what they can afford
            max_principal = max_principal

    return AmountRange(
        min_amount=round(max(min_principal, 0.0), 2),
        max_amount=round(max(max_principal, 0.0), 2),
    )


def find_optimal_timing(
    monthly_capacities: list[MonthlyCapacity],
    tenure_months: int,
) -> TimingWindow:
    """Find the best window to start the loan (Req 7.2).

    Scans all possible start months and picks the window where the
    average surplus over the tenure is highest.
    """
    if not monthly_capacities:
        now = datetime.now(UTC)
        return TimingWindow(
            start_month=now.month, start_year=now.year,
            end_month=now.month, end_year=now.year,
            suitability=TimingSuitability.POOR,
            reason="No cash flow data available",
        )

    n = len(monthly_capacities)
    best_avg = -math.inf
    best_start = 0
    window = min(tenure_months, n)

    for i in range(n - window + 1):
        slice_ = monthly_capacities[i : i + window]
        avg = sum(c.surplus for c in slice_) / len(slice_)
        if avg > best_avg:
            best_avg = avg
            best_start = i

    start = monthly_capacities[best_start]
    end_idx = min(best_start + window - 1, n - 1)
    end = monthly_capacities[end_idx]

    deficit_count = sum(
        1 for c in monthly_capacities[best_start : best_start + window] if c.surplus < 0
    )
    suitability = _classify_timing_suitability(
        best_avg,
        min(c.surplus for c in monthly_capacities[best_start : best_start + window]),
        deficit_count,
        window,
    )

    return TimingWindow(
        start_month=start.month, start_year=start.year,
        end_month=end.month, end_year=end.year,
        suitability=suitability,
        reason=_timing_reason(suitability, best_avg, deficit_count),
        expected_surplus=round(best_avg, 2),
    )


def compute_suggested_terms(
    recommended_amount: AmountRange,
    tenure_months: int,
    interest_rate_annual: float,
    risk_category: str,
) -> SuggestedTerms:
    """Compute suggested loan terms."""
    principal = (recommended_amount.min_amount + recommended_amount.max_amount) / 2
    emi = _principal_to_emi(principal, interest_rate_annual, tenure_months)
    total_repay = emi * tenure_months

    source = _recommend_source(principal, risk_category)

    return SuggestedTerms(
        tenure_months=tenure_months,
        interest_rate_max_pct=interest_rate_annual,
        emi_amount=round(emi, 2),
        total_repayment=round(total_repay, 2),
        source_recommendation=source,
    )


def build_risk_summary(
    risk_category: str,
    risk_score: float,
    dti_ratio: float,
    avg_surplus: float,
    avg_inflow: float,
    key_factors: list[str] | None = None,
) -> RiskSummary:
    """Build a risk summary for guidance context."""
    repay_pct = (avg_surplus / avg_inflow * 100) if avg_inflow > 0 else 0.0
    factors = key_factors or _default_risk_factors(risk_category, dti_ratio)
    return RiskSummary(
        risk_category=risk_category,
        risk_score=risk_score,
        dti_ratio=round(dti_ratio, 4),
        repayment_capacity_pct=round(repay_pct, 2),
        key_risk_factors=factors,
    )


def generate_alternative_options(
    risk_category: str,
    loan_purpose: LoanPurpose,
    recommended_max: float,
) -> list[AlternativeOption]:
    """Generate alternative credit/support options for the borrower."""
    options: list[AlternativeOption] = []

    # SHG loan option for smaller amounts
    if recommended_max < 200_000:
        options.append(AlternativeOption(
            option_type="SHG_LOAN",
            description="Borrow from your Self-Help Group at lower interest",
            estimated_amount=min(recommended_max * 0.6, 50_000),
            advantages=["Lower interest rate", "Flexible repayment", "No formal credit check"],
            disadvantages=["Smaller amount", "Requires active SHG membership"],
        ))

    # Government scheme
    if loan_purpose in (
        LoanPurpose.CROP_CULTIVATION,
        LoanPurpose.LIVESTOCK_PURCHASE,
        LoanPurpose.IRRIGATION,
        LoanPurpose.EQUIPMENT_PURCHASE,
    ):
        options.append(AlternativeOption(
            option_type="GOVERNMENT_SCHEME",
            description="Apply for Kisan Credit Card or other government agricultural scheme",
            estimated_amount=min(recommended_max * 1.5, 300_000),
            advantages=["Subsidized interest (4-7%)", "Insurance coverage", "Government backing"],
            disadvantages=["Lengthy approval process", "Documentation requirements"],
        ))

    # Crop insurance suggestion for cultivation
    if loan_purpose == LoanPurpose.CROP_CULTIVATION:
        options.append(AlternativeOption(
            option_type="CROP_INSURANCE",
            description="Complement loan with Pradhan Mantri Fasal Bima Yojana",
            estimated_amount=0,
            advantages=["Protects against crop failure", "Low premiums", "Government subsidized"],
            disadvantages=["Claims process can be slow", "Coverage may not be complete"],
        ))

    # Debt consolidation warning for high-risk
    if risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH):
        options.append(AlternativeOption(
            option_type="DEBT_RESTRUCTURING",
            description="Consider restructuring existing informal loans before new borrowing",
            estimated_amount=0,
            advantages=["Reduces monthly burden", "Avoids over-indebtedness"],
            disadvantages=["May require negotiation with lenders"],
        ))

    return options


def build_explanation(
    loan_purpose: LoanPurpose,
    risk_summary: RiskSummary,
    timing: TimingWindow,
    amount: AmountRange,
    capacities: list[MonthlyCapacity],
) -> GuidanceExplanation:
    """Build human-readable explanation of guidance reasoning (Req 7.5)."""
    steps: list[ReasoningStep] = []
    caveats: list[str] = []
    step_num = 0

    # Step 1: Risk assessment
    step_num += 1
    risk_impact = "POSITIVE" if risk_summary.risk_category in ("LOW", "MEDIUM") else "NEGATIVE"
    steps.append(ReasoningStep(
        step_number=step_num,
        factor="Risk Profile",
        observation=f"Your risk level is {risk_summary.risk_category} with score {risk_summary.risk_score:.0f}/1000",
        impact=risk_impact,
    ))

    # Step 2: Debt burden
    step_num += 1
    dti_impact = "POSITIVE" if risk_summary.dti_ratio < 0.4 else "NEGATIVE"
    steps.append(ReasoningStep(
        step_number=step_num,
        factor="Current Debt Burden",
        observation=f"Debt-to-income ratio is {risk_summary.dti_ratio:.1%}",
        impact=dti_impact,
    ))

    # Step 3: Cash flow
    step_num += 1
    deficit_months = sum(1 for c in capacities if c.surplus < 0)
    if deficit_months == 0:
        cf_obs = "No months show cash deficit in the forecast period"
        cf_impact = "POSITIVE"
    else:
        cf_obs = f"{deficit_months} out of {len(capacities)} months show cash deficit"
        cf_impact = "NEGATIVE"
    steps.append(ReasoningStep(
        step_number=step_num,
        factor="Cash Flow Stability",
        observation=cf_obs,
        impact=cf_impact,
    ))

    # Step 4: Timing
    step_num += 1
    steps.append(ReasoningStep(
        step_number=step_num,
        factor="Loan Timing",
        observation=timing.reason,
        impact="POSITIVE" if timing.suitability in (TimingSuitability.OPTIMAL, TimingSuitability.GOOD) else "NEUTRAL",
    ))

    # Step 5: Amount
    step_num += 1
    steps.append(ReasoningStep(
        step_number=step_num,
        factor="Recommended Amount",
        observation=(
            f"Based on your repayment capacity, you can safely borrow "
            f"between Rs {amount.min_amount:,.0f} and Rs {amount.max_amount:,.0f}"
        ),
        impact="NEUTRAL",
    ))

    # Confidence
    negative_count = sum(1 for s in steps if s.impact == "NEGATIVE")
    if negative_count == 0:
        confidence = ConfidenceLevel.HIGH
    elif negative_count <= 2:
        confidence = ConfidenceLevel.MEDIUM
    else:
        confidence = ConfidenceLevel.LOW

    # Caveats
    if len(capacities) < 6:
        caveats.append("Limited cash flow data - projections may be less accurate")
    if risk_summary.risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH):
        caveats.append("High risk profile - consider reducing loan amount or improving risk factors first")
    if deficit_months > 3:
        caveats.append("Multiple deficit months detected - ensure emergency fund before borrowing")

    summary = _build_summary_text(loan_purpose, amount, timing, risk_summary)

    return GuidanceExplanation(
        summary=summary,
        reasoning_steps=steps,
        confidence=confidence,
        caveats=caveats,
    )


def build_credit_guidance(
    profile_id: ProfileId,
    loan_purpose: LoanPurpose,
    requested_amount: float | None,
    projections: list[tuple[int, int, float, float]],
    existing_obligations: float,
    risk_category: str,
    risk_score: float,
    dti_ratio: float,
    tenure_months: int = 12,
    interest_rate_annual: float = 9.0,
) -> CreditGuidance:
    """Orchestrate all pure functions to build complete credit guidance.

    Tries the MultiObjectiveCreditOptimiser first; falls back to
    rule-based recommendation if the AI layer is unavailable.
    """
    capacities = compute_monthly_capacities(projections, existing_obligations)

    # ── Try AI-optimised amount / timing / terms ────────────────────
    amount: AmountRange | None = None
    timing: TimingWindow | None = None
    terms: SuggestedTerms | None = None
    ai_reasoning: list[str] = []

    try:
        from services.shared.ai import get_credit_optimiser

        opt = get_credit_optimiser()
        surpluses = [c.surplus for c in capacities]
        avg_surplus = sum(surpluses) / len(surpluses) if surpluses else 0.0

        opt_result = opt.optimise(
            avg_monthly_surplus=avg_surplus,
            risk_score=risk_score,
            risk_category=risk_category,
            dti_ratio=dti_ratio,
            loan_purpose=loan_purpose.value,
            requested_amount=requested_amount,
            interest_rate_annual=interest_rate_annual,
        )

        # Build amount range: ±20% around AI-recommended amount
        ai_min = max(0.0, opt_result.recommended_amount * 0.8)
        ai_max = opt_result.recommended_amount
        amount = AmountRange(
            min_amount=round(ai_min, 2),
            max_amount=round(ai_max, 2),
        )

        # AI-suggested terms
        terms = compute_suggested_terms(
            amount, opt_result.recommended_tenure, interest_rate_annual, risk_category,
        )

        ai_reasoning = opt_result.reasoning
        logger.info(
            "AI credit optimiser applied: amount=%.0f tenure=%d score=%.2f",
            opt_result.recommended_amount, opt_result.recommended_tenure,
            opt_result.affordability_score,
        )
    except Exception:
        logger.warning(
            "AI credit optimiser unavailable, using rules-based guidance",
            exc_info=True,
        )

    # ── Fall back to rule-based if AI didn't produce results ────────
    if amount is None:
        amount = recommend_loan_amount(
            capacities, requested_amount, risk_category, tenure_months, interest_rate_annual,
        )
    if timing is None:
        timing = find_optimal_timing(capacities, tenure_months)
    if terms is None:
        terms = compute_suggested_terms(amount, tenure_months, interest_rate_annual, risk_category)

    avg_surplus = sum(c.surplus for c in capacities) / len(capacities) if capacities else 0.0
    avg_inflow = sum(c.projected_inflow for c in capacities) / len(capacities) if capacities else 0.0
    risk_summ = build_risk_summary(risk_category, risk_score, dti_ratio, avg_surplus, avg_inflow)

    alternatives = generate_alternative_options(risk_category, loan_purpose, amount.max_amount)
    explanation = build_explanation(loan_purpose, risk_summ, timing, amount, capacities)

    # Append AI reasoning to explanation if available
    if ai_reasoning and explanation.summary:
        reasoning_suffix = " | AI insights: " + "; ".join(ai_reasoning[:3])
        from dataclasses import replace as dc_replace
        explanation = dc_replace(explanation, summary=explanation.summary + reasoning_suffix)

    return CreditGuidance(
        guidance_id=generate_id(),
        profile_id=profile_id,
        loan_purpose=loan_purpose,
        requested_amount=requested_amount,
        recommended_amount=amount,
        optimal_timing=timing,
        suggested_terms=terms,
        risk_summary=risk_summ,
        alternative_options=alternatives,
        explanation=explanation,
    )


def optimize_timing_only(
    profile_id: ProfileId,
    projections: list[tuple[int, int, float, float]],
    existing_obligations: float,
    loan_amount: float,
    tenure_months: int = 12,
) -> TimingWindow:
    """Lightweight timing-only recommendation (Req 7.2)."""
    capacities = compute_monthly_capacities(projections, existing_obligations)
    return find_optimal_timing(capacities, tenure_months)


def recommend_amount_only(
    profile_id: ProfileId,
    projections: list[tuple[int, int, float, float]],
    existing_obligations: float,
    risk_category: str,
    tenure_months: int = 12,
    interest_rate_annual: float = 9.0,
) -> AmountRange:
    """Lightweight amount-only recommendation (Req 7.3)."""
    capacities = compute_monthly_capacities(projections, existing_obligations)
    return recommend_loan_amount(
        capacities, None, risk_category, tenure_months, interest_rate_annual,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _month_to_season(month: int) -> str:
    if month in (6, 7, 8, 9, 10):
        return Season.KHARIF
    elif month in (11, 12, 1, 2, 3):
        return Season.RABI
    else:
        return Season.ZAID


def _classify_timing_suitability(
    avg_surplus: float,
    min_surplus: float,
    deficit_count: int,
    total_months: int,
) -> TimingSuitability:
    if deficit_count == 0 and avg_surplus > 5000:
        return TimingSuitability.OPTIMAL
    if deficit_count <= 1 and avg_surplus > 2000:
        return TimingSuitability.GOOD
    if deficit_count <= 2 and avg_surplus > 0:
        return TimingSuitability.ACCEPTABLE
    return TimingSuitability.POOR


def _risk_emi_fraction(risk_category: str) -> float:
    """Fraction of surplus that can safely be used for new EMI."""
    return {
        RiskCategory.LOW: 0.50,
        RiskCategory.MEDIUM: 0.40,
        RiskCategory.HIGH: 0.25,
        RiskCategory.VERY_HIGH: 0.15,
    }.get(risk_category, 0.30)


def _emi_to_principal(emi: float, annual_rate: float, tenure_months: int) -> float:
    """Convert monthly EMI to principal using present value of annuity."""
    if emi <= 0 or tenure_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return emi * tenure_months
    r = annual_rate / 100 / 12
    return emi * (1 - (1 + r) ** -tenure_months) / r


def _principal_to_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Convert principal to monthly EMI."""
    if principal <= 0 or tenure_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / tenure_months
    r = annual_rate / 100 / 12
    return principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)


def _recommend_source(principal: float, risk_category: str) -> str:
    if principal > 100_000:
        return "FORMAL"
    if risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH):
        return "SEMI_FORMAL"
    if principal < 25_000:
        return "SEMI_FORMAL"
    return "FORMAL"


def _default_risk_factors(risk_category: str, dti_ratio: float) -> list[str]:
    factors: list[str] = []
    if dti_ratio > 0.5:
        factors.append("High debt-to-income ratio")
    if risk_category in (RiskCategory.HIGH, RiskCategory.VERY_HIGH):
        factors.append("Elevated risk profile")
    if dti_ratio > 0.3:
        factors.append("Existing debt obligations")
    if not factors:
        factors.append("No significant risk factors identified")
    return factors


def _timing_reason(suitability: TimingSuitability, avg_surplus: float, deficit_count: int) -> str:
    if suitability == TimingSuitability.OPTIMAL:
        return f"Strong cash flow surplus (avg Rs {avg_surplus:,.0f}/month) with no deficit months"
    if suitability == TimingSuitability.GOOD:
        return f"Good cash flow surplus (avg Rs {avg_surplus:,.0f}/month) with minimal deficit risk"
    if suitability == TimingSuitability.ACCEPTABLE:
        return f"Moderate surplus (avg Rs {avg_surplus:,.0f}/month) but {deficit_count} months may see shortfall"
    return f"Weak cash flow (avg Rs {avg_surplus:,.0f}/month) with {deficit_count} deficit months - consider waiting"


def _build_summary_text(
    purpose: LoanPurpose,
    amount: AmountRange,
    timing: TimingWindow,
    risk: RiskSummary,
) -> str:
    purpose_label = purpose.value.replace("_", " ").lower()
    season = _month_to_season(timing.start_month)
    timing_label = f"{timing.start_month}/{timing.start_year}"

    if risk.risk_category in (RiskCategory.LOW, RiskCategory.MEDIUM):
        tone = "You are in a good position to borrow"
    else:
        tone = "Borrowing carries higher risk for you right now"

    return (
        f"{tone}. For {purpose_label}, we recommend borrowing between "
        f"Rs {amount.min_amount:,.0f} and Rs {amount.max_amount:,.0f}. "
        f"The best time to start is around {timing_label} ({season} season). "
        f"Your current debt-to-income ratio is {risk.dti_ratio:.1%}."
    )
