"""Pydantic schemas — request/response DTOs for the Profile API.

These are NOT domain entities. They handle:
- HTTP serialization / deserialization
- Input validation (types, required fields)
- Response shaping (what the client sees)

Domain entities (in domain/models.py) contain business behavior.
These DTOs contain zero business logic.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Nested DTOs
# ---------------------------------------------------------------------------
class PersonalInfoDTO(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    age: int = Field(..., ge=18, le=100)
    gender: str = Field(..., pattern=r"^(M|F|O|male|female|other)$")
    location: str = Field("", min_length=0)
    district: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    dependents: int = Field(0, ge=0, le=20)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{10,13}$")


class LandDetailsDTO(BaseModel):
    owned_acres: float = Field(0, ge=0, le=100)
    leased_acres: float = Field(0, ge=0, le=100)
    irrigated_percentage: float = Field(0, ge=0, le=100)


class CropInfoDTO(BaseModel):
    crop_name: str
    season: str = Field(..., pattern=r"^(KHARIF|RABI|ZAID)$")
    area_acres: float = Field(..., gt=0)
    expected_yield_quintals: float = Field(..., ge=0)
    expected_price_per_quintal: float = Field(..., ge=0)


class LivestockInfoDTO(BaseModel):
    animal_type: str
    count: int = Field(..., gt=0)
    monthly_income: float = Field(0, ge=0)
    monthly_expense: float = Field(0, ge=0)


class MigrationInfoDTO(BaseModel):
    destination: str
    duration_months: int = Field(0, ge=0, le=12)
    monthly_income: float = Field(0, ge=0)
    season: str = Field("KHARIF", pattern=r"^(KHARIF|RABI|ZAID)$")


class LivelihoodInfoDTO(BaseModel):
    primary_occupation: str
    secondary_occupations: list[str] = Field(default_factory=list)
    land_details: LandDetailsDTO | None = None
    crops: list[CropInfoDTO] = Field(default_factory=list)
    livestock: list[LivestockInfoDTO] = Field(default_factory=list)
    migration_patterns: list[MigrationInfoDTO] = Field(default_factory=list)


class IncomeRecordDTO(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    amount: float = Field(..., ge=0)
    source: str
    is_verified: bool = False


class ExpenseRecordDTO(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    amount: float = Field(..., ge=0)
    category: str


class SeasonalFactorDTO(BaseModel):
    season: str = Field(..., pattern=r"^(KHARIF|RABI|ZAID)$")
    income_multiplier: float = Field(..., gt=0)
    expense_multiplier: float = Field(..., gt=0)
    description: str = ""


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class CreateProfileRequest(BaseModel):
    personal_info: PersonalInfoDTO
    livelihood_info: LivelihoodInfoDTO
    income_records: list[IncomeRecordDTO] = Field(default_factory=list)
    expense_records: list[ExpenseRecordDTO] = Field(default_factory=list)
    seasonal_factors: list[SeasonalFactorDTO] = Field(default_factory=list)


class UpdatePersonalInfoRequest(BaseModel):
    personal_info: PersonalInfoDTO


class UpdateLivelihoodRequest(BaseModel):
    livelihood_info: LivelihoodInfoDTO


class AddIncomeRecordsRequest(BaseModel):
    records: list[IncomeRecordDTO] = Field(..., min_length=1)


class AddExpenseRecordsRequest(BaseModel):
    records: list[ExpenseRecordDTO] = Field(..., min_length=1)


class SetSeasonalFactorsRequest(BaseModel):
    factors: list[SeasonalFactorDTO] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class VolatilityMetricsDTO(BaseModel):
    coefficient_of_variation: float
    income_range_ratio: float
    seasonal_variance: float
    months_below_average: int
    volatility_category: str


class ProfileSummaryDTO(BaseModel):
    profile_id: str
    name: str
    location: str
    occupation: str
    volatility_level: str | None = None
    created_at: str


class ProfileDetailDTO(BaseModel):
    profile_id: str
    personal_info: PersonalInfoDTO
    livelihood_info: LivelihoodInfoDTO
    income_records: list[IncomeRecordDTO]
    expense_records: list[ExpenseRecordDTO]
    seasonal_factors: list[SeasonalFactorDTO]
    volatility_metrics: VolatilityMetricsDTO | None = None
    average_monthly_income: float
    average_monthly_expense: float
    monthly_surplus: float
    estimated_annual_income: float
    created_at: datetime
    updated_at: datetime


class PaginatedProfilesDTO(BaseModel):
    items: list[ProfileSummaryDTO]
    cursor: str | None = None
    has_more: bool = False


class ErrorDTO(BaseModel):
    detail: str
    errors: list[dict] = Field(default_factory=list)
