"""Unit tests for Cash Flow domain service."""

from __future__ import annotations

import pytest

from services.cashflow_service.app.domain.models import (
    CashFlowCategory,
    CashFlowRecord,
    FlowDirection,
)
from services.cashflow_service.app.domain.services import CashFlowService
from services.cashflow_service.app.infrastructure.data_providers import (
    StubLoanDataProvider,
    StubMarketDataProvider,
    StubProfileDataProvider,
    StubWeatherDataProvider,
)
from services.shared.events import AsyncInMemoryEventPublisher


# ---------------------------------------------------------------------------
# In-memory repo for testing
# ---------------------------------------------------------------------------
class InMemoryCashFlowRepository:
    """Minimal in-memory repo that satisfies the CashFlowRepository protocol."""

    def __init__(self) -> None:
        self._forecasts: dict[str, object] = {}
        self._records: dict[str, list[CashFlowRecord]] = {}
        self._latest: dict[str, str] = {}
        self._forecast_history: dict[str, list[str]] = {}

    async def save_forecast(self, forecast) -> None:
        self._forecasts[forecast.forecast_id] = forecast
        self._latest[forecast.profile_id] = forecast.forecast_id
        self._forecast_history.setdefault(forecast.profile_id, []).insert(
            0, forecast.forecast_id,
        )

    async def find_forecast_by_id(self, forecast_id):
        return self._forecasts.get(forecast_id)

    async def find_latest_forecast(self, profile_id):
        fid = self._latest.get(profile_id)
        if fid:
            return self._forecasts.get(fid)
        return None

    async def find_forecast_history(self, profile_id, limit=10):
        ids = self._forecast_history.get(profile_id, [])[:limit]
        return [self._forecasts[fid] for fid in ids if fid in self._forecasts]

    async def save_record(self, record: CashFlowRecord) -> None:
        self._records.setdefault(record.profile_id, []).append(record)

    async def save_records(self, records: list[CashFlowRecord]) -> None:
        for r in records:
            await self.save_record(r)

    async def find_records_by_profile(self, profile_id, limit=200):
        return self._records.get(profile_id, [])[:limit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def service():
    repo = InMemoryCashFlowRepository()
    weather = StubWeatherDataProvider()
    market = StubMarketDataProvider()
    profile = StubProfileDataProvider()
    loan = StubLoanDataProvider()
    events = AsyncInMemoryEventPublisher()
    return CashFlowService(
        repo=repo,
        weather_provider=weather,
        market_provider=market,
        profile_provider=profile,
        loan_provider=loan,
        events=events,
    )


def _sample_records_for_profile(profile_id: str) -> list[CashFlowRecord]:
    """Create sample records directly as domain objects."""
    from services.shared.models import generate_id

    records = []
    for year in (2024, 2025):
        for m, amt in [(10, 80000), (11, 50000), (3, 60000), (4, 30000)]:
            records.append(CashFlowRecord(
                record_id=generate_id(),
                profile_id=profile_id,
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=amt, month=m, year=year,
            ))
        for m in range(1, 13):
            records.append(CashFlowRecord(
                record_id=generate_id(),
                profile_id=profile_id,
                category=CashFlowCategory.LABOUR_INCOME,
                direction=FlowDirection.INFLOW,
                amount=8000, month=m, year=year,
            ))
        for m in range(1, 13):
            records.append(CashFlowRecord(
                record_id=generate_id(),
                profile_id=profile_id,
                category=CashFlowCategory.HOUSEHOLD,
                direction=FlowDirection.OUTFLOW,
                amount=6000, month=m, year=year,
            ))
    return records


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestCashFlowService:
    @pytest.mark.asyncio
    async def test_record_cash_flow(self, service: CashFlowService):
        record = await service.record_cash_flow(
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=50000,
            month=10,
            year=2025,
            season="KHARIF",
            notes="Paddy harvest",
        )
        assert record.profile_id == "farmer-001"
        assert record.amount == 50000
        assert record.category == CashFlowCategory.CROP_INCOME

    @pytest.mark.asyncio
    async def test_record_validates_amount(self, service: CashFlowService):
        with pytest.raises(ValueError, match="Amount must be"):
            await service.record_cash_flow(
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=-1000,
                month=10, year=2025,
            )

    @pytest.mark.asyncio
    async def test_record_validates_month(self, service: CashFlowService):
        with pytest.raises(ValueError, match="Month must be"):
            await service.record_cash_flow(
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=5000,
                month=13, year=2025,
            )

    @pytest.mark.asyncio
    async def test_generate_forecast_direct(self, service: CashFlowService):
        profile_id = "farmer-001"
        records = _sample_records_for_profile(profile_id)

        forecast = await service.generate_forecast_direct(
            profile_id=profile_id,
            records=records,
            horizon_months=12,
            start_month=1,
            start_year=2026,
        )
        assert forecast.profile_id == profile_id
        assert len(forecast.monthly_projections) == 12
        assert forecast.repayment_capacity is not None
        assert forecast.repayment_capacity.recommended_emi >= 0

    @pytest.mark.asyncio
    async def test_forecast_persisted_and_retrievable(self, service: CashFlowService):
        profile_id = "farmer-001"
        records = _sample_records_for_profile(profile_id)

        forecast = await service.generate_forecast_direct(
            profile_id=profile_id,
            records=records,
            horizon_months=12,
            start_month=1,
            start_year=2026,
        )

        # Retrieve by ID
        retrieved = await service.get_forecast(forecast.forecast_id)
        assert retrieved is not None
        assert retrieved.forecast_id == forecast.forecast_id

        # Retrieve latest
        latest = await service.get_latest_forecast(profile_id)
        assert latest is not None
        assert latest.forecast_id == forecast.forecast_id

    @pytest.mark.asyncio
    async def test_forecast_too_few_records(self, service: CashFlowService):
        with pytest.raises(ValueError, match="At least"):
            await service.generate_forecast_direct(
                profile_id="farmer-001",
                records=[
                    CashFlowRecord(
                        record_id="r1", profile_id="farmer-001",
                        category=CashFlowCategory.CROP_INCOME,
                        direction=FlowDirection.INFLOW,
                        amount=10000, month=10, year=2025,
                    ),
                ],
                horizon_months=12,
            )

    @pytest.mark.asyncio
    async def test_repayment_capacity_query(self, service: CashFlowService):
        profile_id = "farmer-002"
        records = _sample_records_for_profile(profile_id)

        await service.generate_forecast_direct(
            profile_id=profile_id,
            records=records,
            horizon_months=12,
            start_month=1,
            start_year=2026,
        )

        cap = await service.get_repayment_capacity(profile_id)
        assert cap is not None
        assert cap.recommended_emi >= 0
        assert cap.emergency_reserve >= 0

    @pytest.mark.asyncio
    async def test_timing_recommendations_query(self, service: CashFlowService):
        profile_id = "farmer-003"
        records = _sample_records_for_profile(profile_id)

        await service.generate_forecast_direct(
            profile_id=profile_id,
            records=records,
            horizon_months=12,
            start_month=1,
            start_year=2026,
        )

        windows = await service.get_timing_recommendations(profile_id)
        assert windows is not None
        assert len(windows) >= 1

    @pytest.mark.asyncio
    async def test_no_forecast_returns_none(self, service: CashFlowService):
        assert await service.get_latest_forecast("nonexistent") is None
        assert await service.get_repayment_capacity("nonexistent") is None
        assert await service.get_timing_recommendations("nonexistent") is None

    @pytest.mark.asyncio
    async def test_events_published(self, service: CashFlowService):
        # Record a cash flow → should publish
        await service.record_cash_flow(
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=50000,
            month=10, year=2025,
        )
        # Generate forecast → should publish
        records = _sample_records_for_profile("farmer-001")
        await service.generate_forecast_direct(
            profile_id="farmer-001",
            records=records,
            horizon_months=12,
        )
        # Check events
        events = service._events.events
        types = [e.event_type for e in events]
        assert "cashflow.recorded" in types
        assert "cashflow.forecast_generated" in types

    @pytest.mark.asyncio
    async def test_forecast_history(self, service: CashFlowService):
        profile_id = "farmer-004"
        records = _sample_records_for_profile(profile_id)

        # Generate two forecasts
        await service.generate_forecast_direct(
            profile_id=profile_id, records=records, horizon_months=6,
        )
        f2 = await service.generate_forecast_direct(
            profile_id=profile_id, records=records, horizon_months=12,
        )

        history = await service.get_forecast_history(profile_id)
        assert len(history) == 2
        # Most recent first
        assert history[0].forecast_id == f2.forecast_id
