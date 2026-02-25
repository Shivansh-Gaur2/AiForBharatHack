"""Pydantic DTOs for the Early Warning & Scenario Simulation API.

Domain models are never exposed directly to clients.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from services.shared.models import AlertSeverity, AlertType

from ..domain.models import (
    AlertStatus,
    RecommendationPriority,
    ScenarioType,
)


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class MonitorRequest(BaseModel):
    """Trigger full monitoring pipeline for a profile."""
    profile_id: str


class DirectAlertRequest(BaseModel):
    """Generate an alert from directly provided data."""
    profile_id: str
    dti_ratio: float = Field(default=0.0, ge=0)
    missed_payments: int = Field(default=0, ge=0)
    days_overdue_avg: float = Field(default=0.0, ge=0)
    recent_surplus_trend: list[float] = Field(default_factory=list)
    expected_incomes: list[IncomeEntry] | None = None
    actual_incomes: list[IncomeEntry] | None = None
    risk_category: str | None = None
    alert_type: str | None = None


class IncomeEntry(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    amount: float = Field(ge=0)


# Fix forward reference — DirectAlertRequest uses IncomeEntry
DirectAlertRequest.model_rebuild()


class EscalateAlertRequest(BaseModel):
    new_severity: AlertSeverity
    reason: str = Field(min_length=1, max_length=500)


class BaselineProjection(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    inflow: float = Field(ge=0)
    outflow: float = Field(ge=0)


class ScenarioRequest(BaseModel):
    """Request to run a single scenario simulation."""
    profile_id: str
    scenario_type: ScenarioType
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    income_reduction_pct: float = Field(default=0, ge=0, le=100)
    weather_adjustment: float = Field(default=1.0, ge=0.0, le=2.0)
    market_price_change_pct: float = Field(default=0, ge=-100, le=100)
    duration_months: int = Field(default=6, ge=1, le=60)
    existing_monthly_obligations: float = Field(default=0, ge=0)
    household_monthly_expense: float = Field(default=5000, ge=0)


class DirectScenarioRequest(BaseModel):
    """Run a scenario with directly-provided baseline data."""
    profile_id: str
    scenario_type: ScenarioType
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    income_reduction_pct: float = Field(default=0, ge=0, le=100)
    weather_adjustment: float = Field(default=1.0, ge=0.0, le=2.0)
    market_price_change_pct: float = Field(default=0, ge=-100, le=100)
    duration_months: int = Field(default=6, ge=1, le=60)
    baseline_projections: list[BaselineProjection] = Field(min_length=1)
    existing_monthly_obligations: float = Field(default=0, ge=0)
    household_monthly_expense: float = Field(default=5000, ge=0)


class ScenarioItem(BaseModel):
    """A single scenario in a comparison request."""
    scenario_type: ScenarioType
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    income_reduction_pct: float = Field(default=0, ge=0, le=100)
    weather_adjustment: float = Field(default=1.0, ge=0.0, le=2.0)
    market_price_change_pct: float = Field(default=0, ge=-100, le=100)
    duration_months: int = Field(default=6, ge=1, le=60)
    existing_monthly_obligations: float = Field(default=0, ge=0)
    household_monthly_expense: float = Field(default=5000, ge=0)


class CompareRequest(BaseModel):
    """Compare multiple scenarios."""
    profile_id: str
    scenarios: list[ScenarioItem] = Field(min_length=1, max_length=10)


class DirectCompareRequest(BaseModel):
    """Compare multiple scenarios with directly-provided baseline."""
    profile_id: str
    scenarios: list[ScenarioItem] = Field(min_length=1, max_length=10)
    baseline_projections: list[BaselineProjection] = Field(min_length=1)
    existing_monthly_obligations: float = Field(default=0, ge=0)
    household_monthly_expense: float = Field(default=5000, ge=0)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class RiskFactorSnapshotDTO(BaseModel):
    factor_name: str
    current_value: float
    threshold: float
    severity_contribution: str


class ActionableRecommendationDTO(BaseModel):
    action: str
    rationale: str
    priority: RecommendationPriority
    estimated_impact: str


class AlertDTO(BaseModel):
    alert_id: str
    profile_id: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    risk_factors: list[RiskFactorSnapshotDTO]
    recommendations: list[ActionableRecommendationDTO]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class AlertSummaryDTO(BaseModel):
    alert_id: str
    profile_id: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    created_at: datetime


class AlertListDTO(BaseModel):
    items: list[AlertSummaryDTO]
    count: int


class ScenarioProjectionDTO(BaseModel):
    month: int
    year: int
    baseline_inflow: float
    stressed_inflow: float
    baseline_outflow: float
    stressed_outflow: float
    baseline_net: float
    stressed_net: float


class CapacityImpactDTO(BaseModel):
    original_recommended_emi: float
    stressed_recommended_emi: float
    original_max_emi: float
    stressed_max_emi: float
    original_dscr: float
    stressed_dscr: float
    emi_reduction_pct: float
    can_still_repay: bool


class ScenarioRecommendationDTO(BaseModel):
    recommendation: str
    risk_level: str
    confidence: str
    rationale: str


class ScenarioParamsDTO(BaseModel):
    scenario_type: ScenarioType
    name: str
    description: str
    income_reduction_pct: float
    weather_adjustment: float
    market_price_change_pct: float
    duration_months: int


class SimulationResultDTO(BaseModel):
    simulation_id: str
    profile_id: str
    scenario: ScenarioParamsDTO
    projections: list[ScenarioProjectionDTO]
    capacity_impact: CapacityImpactDTO
    recommendations: list[ScenarioRecommendationDTO]
    overall_risk_level: str
    total_income_loss: float
    months_in_deficit: int
    created_at: datetime


class SimulationSummaryDTO(BaseModel):
    simulation_id: str
    profile_id: str
    scenario_name: str
    scenario_type: ScenarioType
    overall_risk_level: str
    emi_reduction_pct: float
    months_in_deficit: int
    created_at: datetime


class SimulationListDTO(BaseModel):
    items: list[SimulationSummaryDTO]
    count: int


class ComparisonResultDTO(BaseModel):
    profile_id: str
    results: list[SimulationResultDTO]
    count: int


class ErrorDTO(BaseModel):
    detail: str
