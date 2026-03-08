"""FastAPI routes for the Cash Flow service.

Translates HTTP requests <-> domain service calls.
All DTOs live in schemas.py; domain objects are never serialized directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.shared.models import generate_id

from ..domain.models import (
    CashFlowForecast,
    CashFlowRecord,
)
from ..domain.services import CashFlowService
from .schemas import (
    BatchRecordRequest,
    CashFlowForecastDTO,
    CashFlowRecordDTO,
    DirectForecastRequest,
    ForecastAssumptionDTO,
    ForecastHistoryDTO,
    ForecastSummaryDTO,
    GenerateForecastRequest,
    MonthlyProjectionDTO,
    RecordCashFlowRequest,
    RecordsListDTO,
    RepaymentCapacityDTO,
    SeasonalPatternDTO,
    TimingWindowDTO,
    UncertaintyBandDTO,
)

router = APIRouter(prefix="/api/v1/cashflow", tags=["Cash Flow"])

# ---------------------------------------------------------------------------
# Dependency injection (set from main.py)
# ---------------------------------------------------------------------------
_cashflow_service: CashFlowService | None = None


def set_cashflow_service(svc: CashFlowService) -> None:
    global _cashflow_service
    _cashflow_service = svc


def get_cashflow_service() -> CashFlowService:
    assert _cashflow_service is not None, "CashFlowService not wired"
    return _cashflow_service


# ---------------------------------------------------------------------------
# Mappers: Domain -> DTO
# ---------------------------------------------------------------------------
def _record_to_dto(record: CashFlowRecord) -> CashFlowRecordDTO:
    return CashFlowRecordDTO(
        record_id=record.record_id,
        profile_id=record.profile_id,
        category=record.category,
        direction=record.direction,
        amount=record.amount,
        month=record.month,
        year=record.year,
        season=record.season,
        notes=record.notes,
        recorded_at=record.recorded_at,
    )


def _forecast_to_dto(forecast: CashFlowForecast) -> CashFlowForecastDTO:
    best = forecast.get_best_timing_window()
    return CashFlowForecastDTO(
        forecast_id=forecast.forecast_id,
        profile_id=forecast.profile_id,
        forecast_period_start_month=forecast.forecast_period_start_month,
        forecast_period_start_year=forecast.forecast_period_start_year,
        forecast_period_end_month=forecast.forecast_period_end_month,
        forecast_period_end_year=forecast.forecast_period_end_year,
        monthly_projections=[
            MonthlyProjectionDTO(
                month=p.month, year=p.year,
                projected_inflow=p.projected_inflow,
                projected_outflow=p.projected_outflow,
                net_cash_flow=p.net_cash_flow,
                confidence=p.confidence,
                surplus_ratio=p.surplus_ratio,
                notes=p.notes,
            )
            for p in forecast.monthly_projections
        ],
        seasonal_patterns=[
            SeasonalPatternDTO(
                category=s.category, direction=s.direction,
                season=s.season, months=s.months,
                average_monthly_amount=s.average_monthly_amount,
                peak_month=s.peak_month, variability_cv=s.variability_cv,
            )
            for s in forecast.seasonal_patterns
        ],
        uncertainty_bands=[
            UncertaintyBandDTO(
                month=u.month, year=u.year,
                lower_bound=u.lower_bound, expected=u.expected,
                upper_bound=u.upper_bound,
            )
            for u in forecast.uncertainty_bands
        ],
        assumptions=[
            ForecastAssumptionDTO(
                factor=a.factor, description=a.description, impact=a.impact,
            )
            for a in forecast.assumptions
        ],
        repayment_capacity=RepaymentCapacityDTO(
            profile_id=forecast.repayment_capacity.profile_id,
            monthly_surplus_avg=forecast.repayment_capacity.monthly_surplus_avg,
            monthly_surplus_min=forecast.repayment_capacity.monthly_surplus_min,
            max_affordable_emi=forecast.repayment_capacity.max_affordable_emi,
            recommended_emi=forecast.repayment_capacity.recommended_emi,
            emergency_reserve=forecast.repayment_capacity.emergency_reserve,
            annual_repayment_capacity=forecast.repayment_capacity.annual_repayment_capacity,
            debt_service_coverage_ratio=forecast.repayment_capacity.debt_service_coverage_ratio,
            computed_at=forecast.repayment_capacity.computed_at,
        ),
        timing_windows=[
            TimingWindowDTO(
                start_month=t.start_month, start_year=t.start_year,
                end_month=t.end_month, end_year=t.end_year,
                suitability_score=t.suitability_score, reason=t.reason,
            )
            for t in forecast.timing_windows
        ],
        best_timing_window=TimingWindowDTO(
            start_month=best.start_month, start_year=best.start_year,
            end_month=best.end_month, end_year=best.end_year,
            suitability_score=best.suitability_score, reason=best.reason,
        ) if best else None,
        total_projected_inflow=forecast.get_total_projected_inflow(),
        total_projected_outflow=forecast.get_total_projected_outflow(),
        model_version=forecast.model_version,
        created_at=forecast.created_at,
        updated_at=forecast.updated_at,
    )


def _forecast_to_summary(forecast: CashFlowForecast) -> ForecastSummaryDTO:
    best = forecast.get_best_timing_window()
    return ForecastSummaryDTO(
        forecast_id=forecast.forecast_id,
        profile_id=forecast.profile_id,
        forecast_period_start_month=forecast.forecast_period_start_month,
        forecast_period_start_year=forecast.forecast_period_start_year,
        forecast_period_end_month=forecast.forecast_period_end_month,
        forecast_period_end_year=forecast.forecast_period_end_year,
        total_projected_inflow=forecast.get_total_projected_inflow(),
        total_projected_outflow=forecast.get_total_projected_outflow(),
        recommended_emi=forecast.repayment_capacity.recommended_emi,
        best_timing_score=best.suitability_score if best else None,
        model_version=forecast.model_version,
        created_at=forecast.created_at,
    )


# ---------------------------------------------------------------------------
# Routes — Records
# ---------------------------------------------------------------------------
@router.post("/records", response_model=CashFlowRecordDTO, status_code=201)
async def record_cash_flow(req: RecordCashFlowRequest):
    """Record a single cash-flow data point (income or expense)."""
    svc = get_cashflow_service()
    try:
        record = await svc.record_cash_flow(
            profile_id=req.profile_id,
            category=req.category,
            direction=req.direction,
            amount=req.amount,
            month=req.month,
            year=req.year,
            season=req.season.value if req.season else None,
            notes=req.notes,
        )
        return _record_to_dto(record)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/records/batch", response_model=RecordsListDTO, status_code=201)
async def record_batch(req: BatchRecordRequest):
    """Record multiple cash-flow data points at once."""
    svc = get_cashflow_service()
    try:

        from services.shared.models import generate_id

        domain_records = [
            CashFlowRecord(
                record_id=generate_id(),
                profile_id=r.profile_id,
                category=r.category,
                direction=r.direction,
                amount=r.amount,
                month=r.month,
                year=r.year,
                season=r.season,
                notes=r.notes,
            )
            for r in req.records
        ]
        saved = await svc.record_batch(domain_records)
        return RecordsListDTO(
            items=[_record_to_dto(r) for r in saved],
            count=len(saved),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/records/{profile_id}", response_model=RecordsListDTO)
async def get_records(
    profile_id: str,
    limit: int = Query(200, ge=1, le=1000),
):
    """Get all cash-flow records for a profile."""
    svc = get_cashflow_service()
    records = await svc.get_records(profile_id, limit)
    return RecordsListDTO(
        items=[_record_to_dto(r) for r in records],
        count=len(records),
    )


# ---------------------------------------------------------------------------
# Routes — Forecasts
# ---------------------------------------------------------------------------
@router.post("/forecast", response_model=CashFlowForecastDTO, status_code=201)
async def generate_forecast(req: GenerateForecastRequest):
    """Generate a forecast using stored records + cross-service data (Req 3.1)."""
    svc = get_cashflow_service()
    try:
        forecast = await svc.generate_forecast(
            profile_id=req.profile_id,
            horizon_months=req.horizon_months,
            start_month=req.start_month,
            start_year=req.start_year,
            loan_tenure_months=req.loan_tenure_months,
        )
        return _forecast_to_dto(forecast)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/forecast/direct", response_model=CashFlowForecastDTO, status_code=201)
async def generate_forecast_direct(req: DirectForecastRequest):
    """Generate a forecast from directly-provided records (no cross-service calls)."""
    svc = get_cashflow_service()
    try:
        domain_records = [
            CashFlowRecord(
                record_id=generate_id(),
                profile_id=req.profile_id,
                category=r.category,
                direction=r.direction,
                amount=r.amount,
                month=r.month,
                year=r.year,
                season=r.season,
                notes=r.notes,
            )
            for r in req.records
        ]
        forecast = await svc.generate_forecast_direct(
            profile_id=req.profile_id,
            records=domain_records,
            horizon_months=req.horizon_months,
            start_month=req.start_month,
            start_year=req.start_year,
            existing_monthly_obligations=req.existing_monthly_obligations,
            household_monthly_expense=req.household_monthly_expense,
            weather_adjustment=req.weather_adjustment,
            market_adjustment=req.market_adjustment,
            loan_tenure_months=req.loan_tenure_months,
        )
        return _forecast_to_dto(forecast)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/forecast/{forecast_id}", response_model=CashFlowForecastDTO)
async def get_forecast(forecast_id: str):
    """Get a specific forecast by ID."""
    svc = get_cashflow_service()
    forecast = await svc.get_forecast(forecast_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return _forecast_to_dto(forecast)


@router.get("/forecast/profile/{profile_id}", response_model=CashFlowForecastDTO)
async def get_latest_forecast(profile_id: str):
    """Get the most recent forecast for a profile."""
    svc = get_cashflow_service()
    forecast = await svc.get_latest_forecast(profile_id)
    if forecast is None:
        raise HTTPException(status_code=404, detail="No forecast found for this profile")
    return _forecast_to_dto(forecast)


@router.get(
    "/forecast/profile/{profile_id}/history",
    response_model=ForecastHistoryDTO,
)
async def get_forecast_history(
    profile_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """Get forecast history for a profile."""
    svc = get_cashflow_service()
    forecasts = await svc.get_forecast_history(profile_id, limit)
    return ForecastHistoryDTO(
        items=[_forecast_to_summary(f) for f in forecasts],
        count=len(forecasts),
    )


# ---------------------------------------------------------------------------
# Routes — Derived insights
# ---------------------------------------------------------------------------
@router.get("/capacity/{profile_id}", response_model=RepaymentCapacityDTO)
async def get_repayment_capacity(profile_id: str):
    """Get repayment capacity from the latest forecast (Req 3.4)."""
    svc = get_cashflow_service()
    cap = await svc.get_repayment_capacity(profile_id)
    if cap is None:
        raise HTTPException(
            status_code=404,
            detail="No forecast available; generate one first",
        )
    return RepaymentCapacityDTO(
        profile_id=cap.profile_id,
        monthly_surplus_avg=cap.monthly_surplus_avg,
        monthly_surplus_min=cap.monthly_surplus_min,
        max_affordable_emi=cap.max_affordable_emi,
        recommended_emi=cap.recommended_emi,
        emergency_reserve=cap.emergency_reserve,
        annual_repayment_capacity=cap.annual_repayment_capacity,
        debt_service_coverage_ratio=cap.debt_service_coverage_ratio,
        computed_at=cap.computed_at,
    )


@router.get("/timing/{profile_id}", response_model=list[TimingWindowDTO])
async def get_timing_recommendations(profile_id: str):
    """Get credit-timing recommendations from the latest forecast (Req 3.3)."""
    svc = get_cashflow_service()
    windows = await svc.get_timing_recommendations(profile_id)
    if windows is None:
        raise HTTPException(
            status_code=404,
            detail="No forecast available; generate one first",
        )
    return [
        TimingWindowDTO(
            start_month=w.start_month, start_year=w.start_year,
            end_month=w.end_month, end_year=w.end_year,
            suitability_score=w.suitability_score, reason=w.reason,
        )
        for w in windows
    ]


@router.delete("/profile/{profile_id}", status_code=204)
async def delete_profile_cashflow(profile_id: str):
    """Delete all cashflow records and forecasts for a profile (cascade on profile deletion)."""
    svc = get_cashflow_service()
    await svc.delete_profile_data(profile_id)
