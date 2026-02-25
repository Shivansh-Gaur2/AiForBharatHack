"""Pydantic request/response DTOs for the Guidance API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared sub-DTOs
# ---------------------------------------------------------------------------


class BaselineProjection(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2035)
    inflow: float = Field(..., ge=0)
    outflow: float = Field(..., ge=0)


class AmountRangeDTO(BaseModel):
    min_amount: float
    max_amount: float
    currency: str = "INR"


class TimingWindowDTO(BaseModel):
    start_month: int
    start_year: int
    end_month: int
    end_year: int
    suitability: str
    reason: str


class SuggestedTermsDTO(BaseModel):
    tenure_months: int
    interest_rate_max_pct: float
    emi_amount: float
    total_repayment: float
    source_recommendation: str


class RiskSummaryDTO(BaseModel):
    risk_category: str
    risk_score: float
    dti_ratio: float
    repayment_capacity_pct: float
    key_risk_factors: list[str]


class AlternativeOptionDTO(BaseModel):
    option_type: str
    description: str
    estimated_amount: float
    advantages: list[str]
    disadvantages: list[str]


class ReasoningStepDTO(BaseModel):
    step_number: int
    factor: str
    observation: str
    impact: str


class GuidanceExplanationDTO(BaseModel):
    summary: str
    reasoning_steps: list[ReasoningStepDTO]
    confidence: str
    caveats: list[str]


class SeasonalInsightDTO(BaseModel):
    season: str
    avg_monthly_surplus: float
    min_surplus: float
    months_in_deficit: int
    suitability: str


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class GuidanceRequest(BaseModel):
    """Cross-service guidance request — fetches data from all services."""

    profile_id: str = Field(..., min_length=1)
    loan_purpose: str
    requested_amount: float | None = None
    tenure_months: int = Field(12, ge=1, le=120)
    interest_rate_annual: float = Field(9.0, ge=0, le=50)


class DirectGuidanceRequest(BaseModel):
    """Standalone guidance request — caller provides all data."""

    profile_id: str = Field(..., min_length=1)
    loan_purpose: str
    requested_amount: float | None = None
    tenure_months: int = Field(12, ge=1, le=120)
    interest_rate_annual: float = Field(9.0, ge=0, le=50)

    # Data normally fetched from other services
    projections: list[BaselineProjection]
    risk_category: str = "MEDIUM"
    risk_score: float = Field(500.0, ge=0, le=1000)
    dti_ratio: float = Field(0.3, ge=0, le=5.0)
    existing_obligations: float = Field(0.0, ge=0)


class TimingRequest(BaseModel):
    """Cross-service timing request."""

    profile_id: str = Field(..., min_length=1)
    loan_amount: float = Field(..., gt=0)
    tenure_months: int = Field(12, ge=1, le=120)


class AmountRequest(BaseModel):
    """Cross-service amount request."""

    profile_id: str = Field(..., min_length=1)
    tenure_months: int = Field(12, ge=1, le=120)
    interest_rate_annual: float = Field(9.0, ge=0, le=50)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class GuidanceDTO(BaseModel):
    """Full credit guidance response."""

    guidance_id: str
    profile_id: str
    loan_purpose: str
    requested_amount: float | None
    recommended_amount: AmountRangeDTO
    optimal_timing: TimingWindowDTO
    suggested_terms: SuggestedTermsDTO
    risk_summary: RiskSummaryDTO
    alternative_options: list[AlternativeOptionDTO]
    explanation: GuidanceExplanationDTO
    status: str
    created_at: datetime
    expires_at: datetime | None


class GuidanceSummaryDTO(BaseModel):
    """Brief summary for listing."""

    guidance_id: str
    profile_id: str
    loan_purpose: str
    recommended_max: float
    risk_category: str
    status: str
    created_at: datetime


class GuidanceListDTO(BaseModel):
    """List of guidance summaries."""

    items: list[GuidanceSummaryDTO]
    count: int


class TimingDTO(BaseModel):
    """Timing-only response."""

    profile_id: str
    timing: TimingWindowDTO


class AmountDTO(BaseModel):
    """Amount-only response."""

    profile_id: str
    recommended_amount: AmountRangeDTO
