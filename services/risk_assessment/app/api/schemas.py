"""Pydantic DTOs for the Risk Assessment API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from services.shared.models import RiskCategory


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class AssessRiskRequest(BaseModel):
    """Trigger a risk assessment by profile ID."""
    profile_id: str


class DirectRiskInput(BaseModel):
    """All inputs for direct scoring (bypasses cross-service calls)."""
    profile_id: str
    income_volatility_cv: float = Field(ge=0, le=5.0)
    annual_income: float = Field(gt=0)
    months_below_average: int = Field(ge=0, le=24)
    debt_to_income_ratio: float = Field(ge=0)
    total_outstanding: float = Field(ge=0)
    active_loan_count: int = Field(ge=0)
    credit_utilisation: float = Field(ge=0, le=2.0)
    on_time_repayment_ratio: float = Field(ge=0, le=1.0)
    has_defaults: bool = False
    seasonal_variance: float = Field(ge=0, default=0.0)
    crop_diversification_index: float = Field(ge=0, le=1.0, default=0.5)
    weather_risk_score: float = Field(ge=0, le=100, default=0.0)
    market_risk_score: float = Field(ge=0, le=100, default=0.0)
    dependents: int = Field(ge=0, default=0)
    age: int = Field(ge=18, le=100, default=30)
    has_irrigation: bool = False


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class RiskFactorDTO(BaseModel):
    factor_type: str
    score: float
    weight: float
    description: str
    data_points: dict[str, float] = {}


class RiskExplanationDTO(BaseModel):
    summary: str
    key_factors: list[str]
    recommendations: list[str]
    confidence_note: str


class RiskAssessmentDTO(BaseModel):
    assessment_id: str
    profile_id: str
    risk_score: int
    risk_category: RiskCategory
    confidence_level: float
    factors: list[RiskFactorDTO]
    explanation: RiskExplanationDTO
    valid_until: datetime
    model_version: str
    created_at: datetime
    updated_at: datetime


class RiskSummaryDTO(BaseModel):
    assessment_id: str
    profile_id: str
    risk_score: int
    risk_category: RiskCategory
    confidence_level: float
    created_at: datetime


class RiskExplainDTO(BaseModel):
    risk_score: int
    category: str
    summary: str
    key_factors: list[str]
    recommendations: list[str]
    confidence: str
    top_factors: list[dict]


class ErrorDTO(BaseModel):
    detail: str
