"""Shared domain value objects used across all services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ---------------------------------------------------------------------------
# Identifiers (Value Objects)
# ---------------------------------------------------------------------------
ProfileId = str
TrackingId = str
AlertId = str
GuidanceId = str


def generate_id(prefix: str | None = None) -> str:
    """Generate a new unique identifier, optionally with a prefix."""
    uid = str(uuid.uuid4())
    return f"{prefix}-{uid}" if prefix else uid


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class OccupationType(StrEnum):
    FARMER = "FARMER"
    TENANT_FARMER = "TENANT_FARMER"
    AGRICULTURAL_LABORER = "AGRICULTURAL_LABORER"
    SHG_MEMBER = "SHG_MEMBER"
    SEASONAL_MIGRANT = "SEASONAL_MIGRANT"
    LIVESTOCK_REARER = "LIVESTOCK_REARER"
    ARTISAN = "ARTISAN"
    SMALL_TRADER = "SMALL_TRADER"
    OTHER = "OTHER"


class LoanSourceType(StrEnum):
    FORMAL = "FORMAL"           # Banks, NBFC
    SEMI_FORMAL = "SEMI_FORMAL" # MFI, SHG
    INFORMAL = "INFORMAL"       # Moneylender, family


class LoanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    DEFAULTED = "DEFAULTED"
    RESTRUCTURED = "RESTRUCTURED"


class RiskCategory(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(StrEnum):
    INCOME_DEVIATION = "INCOME_DEVIATION"
    REPAYMENT_STRESS = "REPAYMENT_STRESS"
    OVER_INDEBTEDNESS = "OVER_INDEBTEDNESS"
    WEATHER_RISK = "WEATHER_RISK"
    MARKET_RISK = "MARKET_RISK"


class Season(StrEnum):
    KHARIF = "KHARIF"    # Jun–Oct  (monsoon crops)
    RABI = "RABI"        # Nov–Mar  (winter crops)
    ZAID = "ZAID"        # Mar–Jun  (summer crops)


# ---------------------------------------------------------------------------
# Shared Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AmountRange:
    min_amount: float
    max_amount: float
    currency: str = "INR"


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class MonthlyAmount:
    month: int     # 1-12
    year: int
    amount: float
    currency: str = "INR"
