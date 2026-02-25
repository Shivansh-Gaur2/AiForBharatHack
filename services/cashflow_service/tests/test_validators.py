"""Unit tests for Cash Flow validators (Req 8 — Data Quality)."""

from __future__ import annotations

from services.cashflow_service.app.domain.models import (
    CashFlowCategory,
    CashFlowRecord,
    FlowDirection,
)
from services.cashflow_service.app.domain.validators import (
    validate_cash_flow_record,
    validate_forecast_request,
    validate_records_quality,
)


# ---------------------------------------------------------------------------
# Tests: validate_cash_flow_record
# ---------------------------------------------------------------------------
class TestValidateCashFlowRecord:
    def test_valid_record(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=50000,
            month=10,
            year=2025,
        )
        result = validate_cash_flow_record(record)
        assert result.is_valid

    def test_negative_amount(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=-100,
            month=10,
            year=2025,
        )
        result = validate_cash_flow_record(record)
        assert not result.is_valid
        assert any("amount" in e.field.lower() for e in result.errors)

    def test_excessive_amount(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=99_00_000,
            month=10,
            year=2025,
        )
        result = validate_cash_flow_record(record)
        assert not result.is_valid

    def test_invalid_month(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=5000,
            month=13,
            year=2025,
        )
        result = validate_cash_flow_record(record)
        assert not result.is_valid

    def test_invalid_year(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="farmer-001",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=5000,
            month=10,
            year=1990,
        )
        result = validate_cash_flow_record(record)
        assert not result.is_valid

    def test_empty_profile_id(self):
        record = CashFlowRecord(
            record_id="r1",
            profile_id="",
            category=CashFlowCategory.CROP_INCOME,
            direction=FlowDirection.INFLOW,
            amount=5000,
            month=10,
            year=2025,
        )
        result = validate_cash_flow_record(record)
        assert not result.is_valid


# ---------------------------------------------------------------------------
# Tests: validate_forecast_request
# ---------------------------------------------------------------------------
class TestValidateForecastRequest:
    def test_valid_request(self):
        result = validate_forecast_request("farmer-001", 12, 10)
        assert result.is_valid

    def test_empty_profile_id(self):
        result = validate_forecast_request("", 12, 10)
        assert not result.is_valid

    def test_horizon_too_short(self):
        result = validate_forecast_request("farmer-001", 0, 10)
        assert not result.is_valid

    def test_horizon_too_long(self):
        result = validate_forecast_request("farmer-001", 100, 10)
        assert not result.is_valid

    def test_too_few_records(self):
        result = validate_forecast_request("farmer-001", 12, 2)
        assert not result.is_valid

    def test_invalid_weather_adjustment(self):
        result = validate_forecast_request(
            "farmer-001", 12, 10, weather_adjustment=5.0,
        )
        assert not result.is_valid

    def test_invalid_market_adjustment(self):
        result = validate_forecast_request(
            "farmer-001", 12, 10, market_adjustment=0.01,
        )
        assert not result.is_valid


# ---------------------------------------------------------------------------
# Tests: validate_records_quality
# ---------------------------------------------------------------------------
class TestValidateRecordsQuality:
    def test_good_quality(self):
        records = []
        for m in range(1, 7):
            records.append(CashFlowRecord(
                record_id=f"r{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=10000,
                month=m,
                year=2025,
            ))
        result = validate_records_quality(records)
        assert result.is_valid

    def test_empty_records(self):
        result = validate_records_quality([])
        assert not result.is_valid

    def test_too_few_months(self):
        records = [
            CashFlowRecord(
                record_id="r1",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=10000,
                month=10,
                year=2025,
            ),
            CashFlowRecord(
                record_id="r2",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=10000,
                month=10,
                year=2024,
            ),
        ]
        result = validate_records_quality(records)
        assert not result.is_valid

    def test_no_inflow_records(self):
        records = [
            CashFlowRecord(
                record_id=f"r{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.HOUSEHOLD,
                direction=FlowDirection.OUTFLOW,
                amount=5000,
                month=m,
                year=2025,
            )
            for m in range(1, 7)
        ]
        result = validate_records_quality(records)
        assert not result.is_valid

    def test_stale_data(self):
        records = [
            CashFlowRecord(
                record_id=f"r{m}",
                profile_id="farmer-001",
                category=CashFlowCategory.CROP_INCOME,
                direction=FlowDirection.INFLOW,
                amount=10000,
                month=m,
                year=2020,
            )
            for m in range(1, 7)
        ]
        result = validate_records_quality(records)
        assert not result.is_valid
