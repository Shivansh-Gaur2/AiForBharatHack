"""Cash Flow domain service — orchestrates cash-flow use cases.

All business logic flows through here. Infrastructure is injected via constructor.
Publishes domain events on forecast generation (Property 6).
"""

from __future__ import annotations

import os

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import ProfileId, generate_id

from .interfaces import (
    CashFlowRepository,
    LoanDataProvider,
    MarketDataProvider,
    ProfileDataProvider,
    WeatherDataProvider,
)
from .models import (
    CashFlowCategory,
    CashFlowForecast,
    CashFlowRecord,
    FlowDirection,
    RepaymentCapacity,
    TimingWindow,
    build_forecast,
)
from .validators import (
    validate_cash_flow_record,
    validate_forecast_request,
    validate_records_quality,
)


class CashFlowService:
    """Application service for cash-flow prediction and alignment (Req 3)."""

    def __init__(
        self,
        repo: CashFlowRepository,
        weather_provider: WeatherDataProvider,
        market_provider: MarketDataProvider,
        profile_provider: ProfileDataProvider,
        loan_provider: LoanDataProvider,
        events: AsyncEventPublisher,
    ) -> None:
        self._repo = repo
        self._weather = weather_provider
        self._market = market_provider
        self._profile = profile_provider
        self._loan = loan_provider
        self._events = events

    # -- Commands ----------------------------------------------------------

    async def record_cash_flow(
        self,
        profile_id: ProfileId,
        category: CashFlowCategory,
        direction: FlowDirection,
        amount: float,
        month: int,
        year: int,
        season: str | None = None,
        notes: str = "",
    ) -> CashFlowRecord:
        """Record a single cash-flow data point (income or expense)."""
        from services.shared.models import Season

        season_enum = Season(season) if season else None
        record = CashFlowRecord(
            record_id=generate_id(),
            profile_id=profile_id,
            category=category,
            direction=direction,
            amount=amount,
            month=month,
            year=year,
            season=season_enum,
            notes=notes,
        )

        result = validate_cash_flow_record(record)
        if not result.is_valid:
            raise ValueError(
                "Invalid cash-flow record: "
                + "; ".join(e.message for e in result.errors)
            )

        await self._repo.save_record(record)

        await self._events.publish(DomainEvent(
            event_type="cashflow.recorded",
            aggregate_id=record.record_id,
            payload={
                "profile_id": profile_id,
                "category": category.value,
                "direction": direction.value,
                "amount": amount,
                "month": month,
                "year": year,
            },
        ))

        return record

    async def record_batch(
        self,
        records: list[CashFlowRecord],
    ) -> list[CashFlowRecord]:
        """Record multiple cash-flow data points at once."""
        for record in records:
            result = validate_cash_flow_record(record)
            if not result.is_valid:
                raise ValueError(
                    f"Invalid record {record.record_id}: "
                    + "; ".join(e.message for e in result.errors)
                )

        await self._repo.save_records(records)
        return records

    async def generate_forecast(
        self,
        profile_id: ProfileId,
        horizon_months: int = 12,
        start_month: int | None = None,
        start_year: int | None = None,
        loan_tenure_months: int = 12,
    ) -> CashFlowForecast:
        """Generate a full cash-flow forecast with timing alignment (Req 3.1–3.5).

        Integrates external data (weather, market) and cross-service data
        (profile info, loan obligations) for a comprehensive prediction.
        """
        # 1) Fetch historical records
        records = await self._repo.find_records_by_profile(profile_id)

        # Validate request
        result = validate_forecast_request(
            profile_id, horizon_months, len(records),
        )
        if not result.is_valid:
            raise ValueError(
                "Invalid forecast request: "
                + "; ".join(e.message for e in result.errors)
            )

        # Validate data quality (Req 8)
        quality = validate_records_quality(records)
        if not quality.is_valid:
            raise ValueError(
                "Data quality issues: "
                + "; ".join(e.message for e in quality.errors)
            )

        # 2) Fetch external adjustment factors
        profile_info = await self._profile.get_profile_summary(profile_id)
        district = profile_info.get("district", "unknown")
        primary_crop = profile_info.get("primary_crop", "rice")

        weather_adj = await self._weather.get_weather_adjustment(
            district=district, season="current",
        )
        market_adj = await self._market.get_market_adjustment(
            crop=primary_crop, district=district,
        )

        # 3) Fetch existing obligations from Loan Tracker
        monthly_obligations = await self._loan.get_monthly_obligations(profile_id)
        household_expense = profile_info.get("household_monthly_expense", 5000.0)

        # 4) Build forecast
        forecast = build_forecast(
            profile_id=profile_id,
            records=records,
            horizon_months=horizon_months,
            start_month=start_month,
            start_year=start_year,
            existing_monthly_obligations=monthly_obligations,
            household_monthly_expense=household_expense,
            weather_adjustment=weather_adj,
            market_adjustment=market_adj,
            loan_tenure_months=loan_tenure_months,
        )

        # ML-enhanced projections (flag-gated: CASHFLOW_ML_ENABLED=true)
        if os.getenv("CASHFLOW_ML_ENABLED", "false").lower() == "true":
            from services.cashflow_service.ml import cashflow_model as _ml_cf  # lazy
            from .models import ForecastConfidence, MonthlyProjection

            _inflows  = [r.amount for r in records if r.direction == FlowDirection.INFLOW]
            _outflows = [r.amount for r in records if r.direction == FlowDirection.OUTFLOW]
            _avg_in   = sum(_inflows)  / max(len(_inflows),  1) if _inflows  else None
            _avg_out  = sum(_outflows) / max(len(_outflows), 1) if _outflows else None
            _has_irr  = bool(profile_info.get("has_irrigation", False))

            _ml_horizon = _ml_cf.predict_horizon(
                start_month=forecast.forecast_period_start_month,
                start_year=forecast.forecast_period_start_year,
                horizon_months=horizon_months,
                has_irrigation=_has_irr,
                weather_adjustment=weather_adj,
                market_adjustment=market_adj,
                profile_avg_inflow=_avg_in,
                profile_avg_outflow=_avg_out,
            )
            if _ml_horizon is not None:
                _conf = ForecastConfidence.HIGH if len(_inflows) >= 6 else ForecastConfidence.MEDIUM
                forecast.monthly_projections = [
                    MonthlyProjection(
                        month=p["month"],
                        year=p["year"],
                        projected_inflow=p["predicted_inflow"],
                        projected_outflow=p["predicted_outflow"],
                        net_cash_flow=round(
                            p["predicted_inflow"] - p["predicted_outflow"], 2,
                        ),
                        confidence=_conf,
                        notes="ridge-seasonal-v1",
                    )
                    for p in _ml_horizon
                ]
                forecast.model_version = "ridge-seasonal-v1"

        # 5) Persist
        await self._repo.save_forecast(forecast)

        # 6) Publish event
        await self._events.publish(DomainEvent(
            event_type="cashflow.forecast_generated",
            aggregate_id=forecast.forecast_id,
            payload={
                "profile_id": profile_id,
                "horizon_months": horizon_months,
                "projected_annual_inflow": forecast.get_total_projected_inflow(),
                "repayment_capacity": forecast.repayment_capacity.recommended_emi,
            },
        ))

        return forecast

    async def generate_forecast_direct(
        self,
        profile_id: ProfileId,
        records: list[CashFlowRecord],
        horizon_months: int = 12,
        start_month: int | None = None,
        start_year: int | None = None,
        existing_monthly_obligations: float = 0.0,
        household_monthly_expense: float = 5000.0,
        weather_adjustment: float = 1.0,
        market_adjustment: float = 1.0,
        loan_tenure_months: int = 12,
    ) -> CashFlowForecast:
        """Generate a forecast from directly-provided records (no cross-service calls).

        Useful for testing and when all data is already available.
        """
        result = validate_forecast_request(
            profile_id, horizon_months, len(records),
            weather_adjustment=weather_adjustment,
            market_adjustment=market_adjustment,
        )
        if not result.is_valid:
            raise ValueError(
                "Invalid forecast request: "
                + "; ".join(e.message for e in result.errors)
            )

        forecast = build_forecast(
            profile_id=profile_id,
            records=records,
            horizon_months=horizon_months,
            start_month=start_month,
            start_year=start_year,
            existing_monthly_obligations=existing_monthly_obligations,
            household_monthly_expense=household_monthly_expense,
            weather_adjustment=weather_adjustment,
            market_adjustment=market_adjustment,
            loan_tenure_months=loan_tenure_months,
        )

        await self._repo.save_forecast(forecast)

        await self._events.publish(DomainEvent(
            event_type="cashflow.forecast_generated",
            aggregate_id=forecast.forecast_id,
            payload={
                "profile_id": profile_id,
                "horizon_months": horizon_months,
                "projected_annual_inflow": forecast.get_total_projected_inflow(),
            },
        ))

        return forecast

    # -- Queries -----------------------------------------------------------

    async def get_forecast(self, forecast_id: str) -> CashFlowForecast | None:
        """Get a forecast by ID."""
        return await self._repo.find_forecast_by_id(forecast_id)

    async def get_latest_forecast(
        self, profile_id: ProfileId,
    ) -> CashFlowForecast | None:
        """Get the most recent forecast for a profile."""
        return await self._repo.find_latest_forecast(profile_id)

    async def get_forecast_history(
        self, profile_id: ProfileId, limit: int = 10,
    ) -> list[CashFlowForecast]:
        """Get forecast history for a profile."""
        return await self._repo.find_forecast_history(profile_id, limit)

    async def get_records(
        self, profile_id: ProfileId, limit: int = 200,
    ) -> list[CashFlowRecord]:
        """Get all cash-flow records for a profile."""
        return await self._repo.find_records_by_profile(profile_id, limit)

    async def get_repayment_capacity(
        self, profile_id: ProfileId,
    ) -> RepaymentCapacity | None:
        """Get repayment capacity from the latest forecast."""
        forecast = await self._repo.find_latest_forecast(profile_id)
        if forecast is None:
            return None
        return forecast.repayment_capacity

    async def get_timing_recommendations(
        self, profile_id: ProfileId,
    ) -> list[TimingWindow] | None:
        """Get credit timing recommendations from the latest forecast."""
        forecast = await self._repo.find_latest_forecast(profile_id)
        if forecast is None:
            return None
        return forecast.timing_windows
