"""Pydantic DTOs for the Cash Flow Service API.

These are the interface-layer data-transfer objects.
Domain models are never exposed directly to clients.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from services.shared.models import Season

from ..domain.models import CashFlowCategory, FlowDirection, ForecastConfidence


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class RecordCashFlowRequest(BaseModel):
    profile_id: str
    category: CashFlowCategory
    direction: FlowDirection
    amount: float = Field(ge=0, le=50_00_000, description="Amount in INR")
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    season: Season | None = None
    notes: str = ""


class BatchRecordRequest(BaseModel):
    records: list[RecordCashFlowRequest] = Field(min_length=1, max_length=500)


class GenerateForecastRequest(BaseModel):
    profile_id: str
    horizon_months: int = Field(default=12, ge=1, le=60)
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    loan_tenure_months: int = Field(default=12, ge=1, le=240)


class DirectForecastRequest(BaseModel):
    """Generate a forecast from directly-provided records (no cross-service calls)."""
    profile_id: str
    records: list[RecordCashFlowRequest] = Field(min_length=3)
    horizon_months: int = Field(default=12, ge=1, le=60)
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    existing_monthly_obligations: float = Field(default=0.0, ge=0)
    household_monthly_expense: float = Field(default=5000.0, ge=0)
    weather_adjustment: float = Field(default=1.0, ge=0.1, le=2.0)
    market_adjustment: float = Field(default=1.0, ge=0.1, le=2.0)
    loan_tenure_months: int = Field(default=12, ge=1, le=240)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class CashFlowRecordDTO(BaseModel):
    record_id: str
    profile_id: str
    category: CashFlowCategory
    direction: FlowDirection
    amount: float
    month: int
    year: int
    season: Season | None = None
    notes: str = ""
    recorded_at: datetime


class MonthlyProjectionDTO(BaseModel):
    month: int
    year: int
    projected_inflow: float
    projected_outflow: float
    net_cash_flow: float
    confidence: ForecastConfidence
    surplus_ratio: float
    notes: str = ""


class SeasonalPatternDTO(BaseModel):
    category: CashFlowCategory
    direction: FlowDirection
    season: Season
    months: list[int]
    average_monthly_amount: float
    peak_month: int
    variability_cv: float


class UncertaintyBandDTO(BaseModel):
    month: int
    year: int
    lower_bound: float
    expected: float
    upper_bound: float


class ForecastAssumptionDTO(BaseModel):
    factor: str
    description: str
    impact: str


class RepaymentCapacityDTO(BaseModel):
    profile_id: str
    monthly_surplus_avg: float
    monthly_surplus_min: float
    max_affordable_emi: float
    recommended_emi: float
    emergency_reserve: float
    annual_repayment_capacity: float
    debt_service_coverage_ratio: float
    computed_at: datetime


class TimingWindowDTO(BaseModel):
    start_month: int
    start_year: int
    end_month: int
    end_year: int
    suitability_score: float
    reason: str


class CashFlowForecastDTO(BaseModel):
    forecast_id: str
    profile_id: str
    forecast_period_start_month: int
    forecast_period_start_year: int
    forecast_period_end_month: int
    forecast_period_end_year: int
    monthly_projections: list[MonthlyProjectionDTO]
    seasonal_patterns: list[SeasonalPatternDTO]
    uncertainty_bands: list[UncertaintyBandDTO]
    assumptions: list[ForecastAssumptionDTO]
    repayment_capacity: RepaymentCapacityDTO
    timing_windows: list[TimingWindowDTO]
    best_timing_window: TimingWindowDTO | None = None
    total_projected_inflow: float
    total_projected_outflow: float
    model_version: str
    created_at: datetime
    updated_at: datetime


class ForecastSummaryDTO(BaseModel):
    forecast_id: str
    profile_id: str
    forecast_period_start_month: int
    forecast_period_start_year: int
    forecast_period_end_month: int
    forecast_period_end_year: int
    total_projected_inflow: float
    total_projected_outflow: float
    recommended_emi: float
    best_timing_score: float | None = None
    model_version: str
    created_at: datetime


class RecordsListDTO(BaseModel):
    items: list[CashFlowRecordDTO]
    count: int


class ForecastHistoryDTO(BaseModel):
    items: list[ForecastSummaryDTO]
    count: int


class ErrorDTO(BaseModel):
    detail: str
