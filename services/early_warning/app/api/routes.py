"""FastAPI routes for the Early Warning & Scenario Simulation service.

Translates HTTP requests <-> domain service calls.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..domain.models import (
    Alert,
    ScenarioParameters,
    SimulationResult,
)
from ..domain.services import EarlyWarningService
from .schemas import (
    ActionableRecommendationDTO,
    AlertDTO,
    AlertListDTO,
    AlertSummaryDTO,
    CapacityImpactDTO,
    CompareRequest,
    ComparisonResultDTO,
    DirectAlertRequest,
    DirectCompareRequest,
    DirectScenarioRequest,
    EscalateAlertRequest,
    MonitorRequest,
    RiskFactorSnapshotDTO,
    ScenarioItem,
    ScenarioParamsDTO,
    ScenarioProjectionDTO,
    ScenarioRecommendationDTO,
    ScenarioRequest,
    SimulationListDTO,
    SimulationResultDTO,
    SimulationSummaryDTO,
)

router = APIRouter(prefix="/api/v1/early-warning", tags=["Early Warning & Scenarios"])

# ---------------------------------------------------------------------------
# Service injection (set from main.py)
# ---------------------------------------------------------------------------
_ew_service: EarlyWarningService | None = None


def set_early_warning_service(svc: EarlyWarningService) -> None:
    global _ew_service
    _ew_service = svc


def get_early_warning_service() -> EarlyWarningService:
    if _ew_service is None:
        raise RuntimeError("EarlyWarningService not initialised")
    return _ew_service


# ---------------------------------------------------------------------------
# DTO converters
# ---------------------------------------------------------------------------
def _alert_to_dto(alert: Alert) -> AlertDTO:
    return AlertDTO(
        alert_id=alert.alert_id,
        profile_id=alert.profile_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        description=alert.description,
        risk_factors=[
            RiskFactorSnapshotDTO(
                factor_name=f.factor_name,
                current_value=f.current_value,
                threshold=f.threshold,
                severity_contribution=f.severity_contribution,
            )
            for f in alert.risk_factors
        ],
        recommendations=[
            ActionableRecommendationDTO(
                action=r.action,
                rationale=r.rationale,
                priority=r.priority,
                estimated_impact=r.estimated_impact,
            )
            for r in alert.recommendations
        ],
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
    )


def _alert_to_summary(alert: Alert) -> AlertSummaryDTO:
    return AlertSummaryDTO(
        alert_id=alert.alert_id,
        profile_id=alert.profile_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        title=alert.title,
        created_at=alert.created_at,
    )


def _simulation_to_dto(result: SimulationResult) -> SimulationResultDTO:
    return SimulationResultDTO(
        simulation_id=result.simulation_id,
        profile_id=result.profile_id,
        scenario=ScenarioParamsDTO(
            scenario_type=result.scenario.scenario_type,
            name=result.scenario.name,
            description=result.scenario.description,
            income_reduction_pct=result.scenario.income_reduction_pct,
            weather_adjustment=result.scenario.weather_adjustment,
            market_price_change_pct=result.scenario.market_price_change_pct,
            duration_months=result.scenario.duration_months,
        ),
        projections=[
            ScenarioProjectionDTO(
                month=p.month, year=p.year,
                baseline_inflow=p.baseline_inflow,
                stressed_inflow=p.stressed_inflow,
                baseline_outflow=p.baseline_outflow,
                stressed_outflow=p.stressed_outflow,
                baseline_net=p.baseline_net,
                stressed_net=p.stressed_net,
            )
            for p in result.projections
        ],
        capacity_impact=CapacityImpactDTO(
            original_recommended_emi=result.capacity_impact.original_recommended_emi,
            stressed_recommended_emi=result.capacity_impact.stressed_recommended_emi,
            original_max_emi=result.capacity_impact.original_max_emi,
            stressed_max_emi=result.capacity_impact.stressed_max_emi,
            original_dscr=result.capacity_impact.original_dscr,
            stressed_dscr=result.capacity_impact.stressed_dscr,
            emi_reduction_pct=result.capacity_impact.emi_reduction_pct,
            can_still_repay=result.capacity_impact.can_still_repay,
        ),
        recommendations=[
            ScenarioRecommendationDTO(
                recommendation=r.recommendation,
                risk_level=r.risk_level,
                confidence=r.confidence,
                rationale=r.rationale,
            )
            for r in result.recommendations
        ],
        overall_risk_level=result.overall_risk_level,
        total_income_loss=result.get_total_income_loss(),
        months_in_deficit=result.months_in_deficit(),
        created_at=result.created_at,
    )


def _simulation_to_summary(result: SimulationResult) -> SimulationSummaryDTO:
    return SimulationSummaryDTO(
        simulation_id=result.simulation_id,
        profile_id=result.profile_id,
        scenario_name=result.scenario.name,
        scenario_type=result.scenario.scenario_type,
        overall_risk_level=result.overall_risk_level,
        emi_reduction_pct=result.capacity_impact.emi_reduction_pct,
        months_in_deficit=result.months_in_deficit(),
        created_at=result.created_at,
    )


def _scenario_item_to_params(item: ScenarioItem) -> ScenarioParameters:
    return ScenarioParameters(
        scenario_type=item.scenario_type,
        name=item.name,
        description=item.description,
        income_reduction_pct=item.income_reduction_pct,
        weather_adjustment=item.weather_adjustment,
        market_price_change_pct=item.market_price_change_pct,
        duration_months=item.duration_months,
        existing_monthly_obligations=item.existing_monthly_obligations,
        household_monthly_expense=item.household_monthly_expense,
    )


# ---------------------------------------------------------------------------
# Alert Routes
# ---------------------------------------------------------------------------
@router.post("/monitor", response_model=AlertDTO, status_code=201)
async def monitor_and_alert(req: MonitorRequest):
    """Run full monitoring pipeline and generate alert (Req 5.1–5.4)."""
    svc = get_early_warning_service()
    try:
        alert = await svc.monitor_and_alert(req.profile_id)
        return _alert_to_dto(alert)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/alerts/direct", response_model=AlertDTO, status_code=201)
async def generate_alert_direct(req: DirectAlertRequest):
    """Generate an alert from directly-provided data."""
    svc = get_early_warning_service()
    try:
        expected = [(ie.month, ie.year, ie.amount) for ie in req.expected_incomes] if req.expected_incomes else None
        actual = [(ie.month, ie.year, ie.amount) for ie in req.actual_incomes] if req.actual_incomes else None

        alert = await svc.generate_alert_direct(
            profile_id=req.profile_id,
            dti_ratio=req.dti_ratio,
            missed_payments=req.missed_payments,
            days_overdue_avg=req.days_overdue_avg,
            recent_surplus_trend=req.recent_surplus_trend,
            expected_incomes=expected,
            actual_incomes=actual,
            risk_category=req.risk_category,
            alert_type=req.alert_type,
        )
        return _alert_to_dto(alert)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/alerts/{alert_id}", response_model=AlertDTO)
async def get_alert(alert_id: str):
    """Get a specific alert by ID."""
    svc = get_early_warning_service()
    alert = await svc.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_dto(alert)


@router.get("/alerts/profile/{profile_id}", response_model=AlertListDTO)
async def get_profile_alerts(
    profile_id: str,
    limit: int = Query(50, ge=1, le=500),
):
    """Get all alerts for a profile."""
    svc = get_early_warning_service()
    alerts = await svc.get_alerts_for_profile(profile_id, limit)
    return AlertListDTO(
        items=[_alert_to_summary(a) for a in alerts],
        count=len(alerts),
    )


@router.get("/alerts/profile/{profile_id}/active", response_model=AlertListDTO)
async def get_active_alerts(profile_id: str):
    """Get active (non-resolved) alerts for a profile."""
    svc = get_early_warning_service()
    alerts = await svc.get_active_alerts(profile_id)
    return AlertListDTO(
        items=[_alert_to_summary(a) for a in alerts],
        count=len(alerts),
    )


@router.post("/alerts/{alert_id}/escalate", response_model=AlertDTO)
async def escalate_alert(alert_id: str, req: EscalateAlertRequest):
    """Escalate an alert to a higher severity (Req 5.3)."""
    svc = get_early_warning_service()
    try:
        alert = await svc.escalate_alert(alert_id, req.new_severity, req.reason)
        return _alert_to_dto(alert)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertDTO)
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    svc = get_early_warning_service()
    try:
        alert = await svc.acknowledge_alert(alert_id)
        return _alert_to_dto(alert)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.post("/alerts/{alert_id}/resolve", response_model=AlertDTO)
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    svc = get_early_warning_service()
    try:
        alert = await svc.resolve_alert(alert_id)
        return _alert_to_dto(alert)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


# ---------------------------------------------------------------------------
# Scenario Simulation Routes
# ---------------------------------------------------------------------------
@router.post("/scenarios/simulate", response_model=SimulationResultDTO, status_code=201)
async def run_scenario(req: ScenarioRequest):
    """Run a single scenario simulation (Req 6.1–6.5)."""
    svc = get_early_warning_service()
    try:
        params = ScenarioParameters(
            scenario_type=req.scenario_type,
            name=req.name,
            description=req.description,
            income_reduction_pct=req.income_reduction_pct,
            weather_adjustment=req.weather_adjustment,
            market_price_change_pct=req.market_price_change_pct,
            duration_months=req.duration_months,
            existing_monthly_obligations=req.existing_monthly_obligations,
            household_monthly_expense=req.household_monthly_expense,
        )
        result = await svc.run_scenario(req.profile_id, params)
        return _simulation_to_dto(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/scenarios/simulate/direct", response_model=SimulationResultDTO, status_code=201)
async def run_scenario_direct(req: DirectScenarioRequest):
    """Run a scenario with directly-provided baseline data."""
    svc = get_early_warning_service()
    try:
        params = ScenarioParameters(
            scenario_type=req.scenario_type,
            name=req.name,
            description=req.description,
            income_reduction_pct=req.income_reduction_pct,
            weather_adjustment=req.weather_adjustment,
            market_price_change_pct=req.market_price_change_pct,
            duration_months=req.duration_months,
        )
        baseline = [(b.month, b.year, b.inflow, b.outflow) for b in req.baseline_projections]
        result = await svc.run_scenario_direct(
            profile_id=req.profile_id,
            params=params,
            baseline_projections=baseline,
            existing_obligations=req.existing_monthly_obligations,
            household_expense=req.household_monthly_expense,
        )
        return _simulation_to_dto(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/scenarios/compare", response_model=ComparisonResultDTO, status_code=201)
async def compare_scenarios(req: CompareRequest):
    """Compare multiple scenarios side-by-side (Req 6.1)."""
    svc = get_early_warning_service()
    try:
        params_list = [_scenario_item_to_params(s) for s in req.scenarios]
        results = await svc.compare_scenarios(req.profile_id, params_list)
        return ComparisonResultDTO(
            profile_id=req.profile_id,
            results=[_simulation_to_dto(r) for r in results],
            count=len(results),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/scenarios/compare/direct", response_model=ComparisonResultDTO, status_code=201)
async def compare_scenarios_direct(req: DirectCompareRequest):
    """Compare multiple scenarios with directly-provided baseline data."""
    svc = get_early_warning_service()
    try:
        params_list = [_scenario_item_to_params(s) for s in req.scenarios]
        baseline = [(b.month, b.year, b.inflow, b.outflow) for b in req.baseline_projections]
        results = await svc.compare_scenarios_direct(
            profile_id=req.profile_id,
            scenarios=params_list,
            baseline_projections=baseline,
            existing_obligations=req.existing_monthly_obligations,
            household_expense=req.household_monthly_expense,
        )
        return ComparisonResultDTO(
            profile_id=req.profile_id,
            results=[_simulation_to_dto(r) for r in results],
            count=len(results),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/scenarios/{simulation_id}", response_model=SimulationResultDTO)
async def get_simulation(simulation_id: str):
    """Get a specific simulation result by ID."""
    svc = get_early_warning_service()
    result = await svc.get_simulation(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return _simulation_to_dto(result)


@router.get("/scenarios/profile/{profile_id}/history", response_model=SimulationListDTO)
async def get_simulation_history(
    profile_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get simulation history for a profile."""
    svc = get_early_warning_service()
    results = await svc.get_simulation_history(profile_id, limit)
    return SimulationListDTO(
        items=[_simulation_to_summary(r) for r in results],
        count=len(results),
    )
