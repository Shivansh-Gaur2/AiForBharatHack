"""Domain validators for cash-flow data (Req 8 — Data Quality)."""

from __future__ import annotations

from datetime import UTC, datetime

from services.shared.validation import ValidationError, ValidationResult

from .models import CashFlowRecord, FlowDirection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_RECORD_AMOUNT = 0.0
MAX_RECORD_AMOUNT = 50_00_000        # 50 lakh INR
MAX_HORIZON_MONTHS = 60              # 5-year max projection
MIN_HORIZON_MONTHS = 1
MIN_RECORDS_FOR_FORECAST = 3         # need some history
MAX_WEATHER_ADJUSTMENT = 2.0
MIN_WEATHER_ADJUSTMENT = 0.1
MAX_MARKET_ADJUSTMENT = 2.0
MIN_MARKET_ADJUSTMENT = 0.1


def validate_cash_flow_record(record: CashFlowRecord) -> ValidationResult:
    """Validate a single cash-flow record (Req 8 — Data Quality)."""
    errors: list[ValidationError] = []

    if record.amount < MIN_RECORD_AMOUNT:
        errors.append(ValidationError(
            field="amount",
            message=f"Amount must be >= {MIN_RECORD_AMOUNT}",
            value=record.amount,
        ))

    if record.amount > MAX_RECORD_AMOUNT:
        errors.append(ValidationError(
            field="amount",
            message=f"Amount must be <= {MAX_RECORD_AMOUNT}",
            value=record.amount,
        ))

    if not 1 <= record.month <= 12:
        errors.append(ValidationError(
            field="month",
            message="Month must be between 1 and 12",
            value=record.month,
        ))

    if record.year < 2000 or record.year > 2100:
        errors.append(ValidationError(
            field="year",
            message="Year must be between 2000 and 2100",
            value=record.year,
        ))

    if not record.profile_id:
        errors.append(ValidationError(
            field="profile_id",
            message="Profile ID is required",
            value=record.profile_id,
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_forecast_request(
    profile_id: str,
    horizon_months: int,
    records_count: int,
    weather_adjustment: float = 1.0,
    market_adjustment: float = 1.0,
) -> ValidationResult:
    """Validate a forecast generation request."""
    errors: list[ValidationError] = []

    if not profile_id:
        errors.append(ValidationError(
            field="profile_id",
            message="Profile ID is required",
            value=profile_id,
        ))

    if horizon_months < MIN_HORIZON_MONTHS:
        errors.append(ValidationError(
            field="horizon_months",
            message=f"Horizon must be >= {MIN_HORIZON_MONTHS} months",
            value=horizon_months,
        ))

    if horizon_months > MAX_HORIZON_MONTHS:
        errors.append(ValidationError(
            field="horizon_months",
            message=f"Horizon must be <= {MAX_HORIZON_MONTHS} months",
            value=horizon_months,
        ))

    if records_count < MIN_RECORDS_FOR_FORECAST:
        errors.append(ValidationError(
            field="records_count",
            message=f"At least {MIN_RECORDS_FOR_FORECAST} historical records needed",
            value=records_count,
        ))

    if not (MIN_WEATHER_ADJUSTMENT <= weather_adjustment <= MAX_WEATHER_ADJUSTMENT):
        errors.append(ValidationError(
            field="weather_adjustment",
            message=f"Weather adjustment must be between {MIN_WEATHER_ADJUSTMENT} and {MAX_WEATHER_ADJUSTMENT}",
            value=weather_adjustment,
        ))

    if not (MIN_MARKET_ADJUSTMENT <= market_adjustment <= MAX_MARKET_ADJUSTMENT):
        errors.append(ValidationError(
            field="market_adjustment",
            message=f"Market adjustment must be between {MIN_MARKET_ADJUSTMENT} and {MAX_MARKET_ADJUSTMENT}",
            value=market_adjustment,
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_records_quality(records: list[CashFlowRecord]) -> ValidationResult:
    """Assess data quality of a batch of records (Req 8)."""
    errors: list[ValidationError] = []

    if not records:
        errors.append(ValidationError(
            field="records",
            message="No records provided",
        ))
        return ValidationResult.fail(errors)

    # Check for reasonable spread across months
    months_covered = {r.month for r in records}
    if len(months_covered) < 3:
        errors.append(ValidationError(
            field="records",
            message=f"Records cover only {len(months_covered)} months; need at least 3 for seasonal analysis",
            value=len(months_covered),
        ))

    # Check for both inflows and outflows
    directions = {r.direction for r in records}
    if FlowDirection.INFLOW not in directions:
        errors.append(ValidationError(
            field="records",
            message="No inflow records found; need income data for forecast",
        ))

    # Check for data recency
    latest_year = max(r.year for r in records)
    current_year = datetime.now(UTC).year
    if latest_year < current_year - 2:
        errors.append(ValidationError(
            field="records",
            message=f"Most recent data is from {latest_year}; need more recent data",
            value=latest_year,
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)
