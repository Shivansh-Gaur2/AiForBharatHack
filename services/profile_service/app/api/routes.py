"""FastAPI routes — translates HTTP ↔ domain calls.

This layer:
1. Deserializes HTTP request → Pydantic DTO
2. Maps DTO → domain objects
3. Calls domain service
4. Maps domain result → response DTO
5. Returns HTTP response

Zero business logic here.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from services.profile_service.app.domain.models import (
    CropInfo,
    ExpenseRecord,
    IncomeRecord,
    LandDetails,
    LivelihoodInfo,
    LivestockInfo,
    MigrationInfo,
    PersonalInfo,
    SeasonalFactor,
)
from services.profile_service.app.domain.services import ProfileService
from services.shared.models import OccupationType, Season

from .schemas import (
    AddExpenseRecordsRequest,
    AddIncomeRecordsRequest,
    CreateProfileRequest,
    PaginatedProfilesDTO,
    ProfileDetailDTO,
    ProfileSummaryDTO,
    SetSeasonalFactorsRequest,
    UpdateLivelihoodRequest,
    UpdatePersonalInfoRequest,
    VolatilityMetricsDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


# ---------------------------------------------------------------------------
# Dependency — will be overridden in main.py with real implementations
# ---------------------------------------------------------------------------
_profile_service: ProfileService | None = None


def get_profile_service() -> ProfileService:
    if _profile_service is None:
        raise RuntimeError("ProfileService not initialized")
    return _profile_service


def set_profile_service(service: ProfileService) -> None:
    global _profile_service
    _profile_service = service


# ---------------------------------------------------------------------------
# DTO → Domain mappers
# ---------------------------------------------------------------------------
def _to_personal_info(dto) -> PersonalInfo:
    return PersonalInfo(
        name=dto.name,
        age=dto.age,
        gender=dto.gender,
        district=dto.district,
        state=dto.state,
        dependents=dto.dependents,
        phone=dto.phone,
    )


def _to_livelihood_info(dto) -> LivelihoodInfo:
    return LivelihoodInfo(
        primary_occupation=OccupationType(dto.primary_occupation),
        secondary_occupations=[OccupationType(o) for o in dto.secondary_occupations],
        land_holding=LandDetails(
            total_acres=dto.land_holding.total_acres,
            irrigated_acres=dto.land_holding.irrigated_acres,
            rain_fed_acres=dto.land_holding.rain_fed_acres,
            ownership_type=dto.land_holding.ownership_type,
        ) if dto.land_holding else None,
        crop_patterns=[
            CropInfo(
                crop_name=c.crop_name,
                season=Season(c.season),
                area_acres=c.area_acres,
                expected_yield_quintals=c.expected_yield_quintals,
                expected_price_per_quintal=c.expected_price_per_quintal,
            ) for c in dto.crop_patterns
        ],
        livestock=[
            LivestockInfo(
                animal_type=l.animal_type,
                count=l.count,
                monthly_income=l.monthly_income,
                monthly_expense=l.monthly_expense,
            ) for l in dto.livestock
        ],
        migration_patterns=[
            MigrationInfo(
                destination=m.destination,
                months=m.months,
                monthly_income=m.monthly_income,
            ) for m in dto.migration_patterns
        ],
    )


def _to_income_records(dtos) -> list[IncomeRecord]:
    return [
        IncomeRecord(
            month=r.month, year=r.year, amount=r.amount,
            source=r.source, is_verified=r.is_verified,
        ) for r in dtos
    ]


def _to_expense_records(dtos) -> list[ExpenseRecord]:
    return [
        ExpenseRecord(
            month=r.month, year=r.year, amount=r.amount, category=r.category,
        ) for r in dtos
    ]


def _to_seasonal_factors(dtos) -> list[SeasonalFactor]:
    return [
        SeasonalFactor(
            season=Season(f.season),
            income_multiplier=f.income_multiplier,
            expense_multiplier=f.expense_multiplier,
            notes=f.notes,
        ) for f in dtos
    ]


# ---------------------------------------------------------------------------
# Domain → Response DTO mappers
# ---------------------------------------------------------------------------
def _to_profile_detail(profile) -> ProfileDetailDTO:
    from .schemas import (
        CropInfoDTO,
        ExpenseRecordDTO,
        IncomeRecordDTO,
        LandDetailsDTO,
        LivelihoodInfoDTO,
        LivestockInfoDTO,
        MigrationInfoDTO,
        PersonalInfoDTO,
        SeasonalFactorDTO,
    )

    return ProfileDetailDTO(
        profile_id=profile.profile_id,
        personal_info=PersonalInfoDTO(
            name=profile.personal_info.name,
            age=profile.personal_info.age,
            gender=profile.personal_info.gender,
            district=profile.personal_info.district,
            state=profile.personal_info.state,
            dependents=profile.personal_info.dependents,
            phone=profile.personal_info.phone,
        ),
        livelihood_info=LivelihoodInfoDTO(
            primary_occupation=profile.livelihood_info.primary_occupation.value,
            secondary_occupations=[o.value for o in profile.livelihood_info.secondary_occupations],
            land_holding=LandDetailsDTO(
                total_acres=profile.livelihood_info.land_holding.total_acres,
                irrigated_acres=profile.livelihood_info.land_holding.irrigated_acres,
                rain_fed_acres=profile.livelihood_info.land_holding.rain_fed_acres,
                ownership_type=profile.livelihood_info.land_holding.ownership_type,
            ) if profile.livelihood_info.land_holding else None,
            crop_patterns=[
                CropInfoDTO(
                    crop_name=c.crop_name, season=c.season.value,
                    area_acres=c.area_acres,
                    expected_yield_quintals=c.expected_yield_quintals,
                    expected_price_per_quintal=c.expected_price_per_quintal,
                ) for c in profile.livelihood_info.crop_patterns
            ],
            livestock=[
                LivestockInfoDTO(
                    animal_type=l.animal_type, count=l.count,
                    monthly_income=l.monthly_income, monthly_expense=l.monthly_expense,
                ) for l in profile.livelihood_info.livestock
            ],
            migration_patterns=[
                MigrationInfoDTO(
                    destination=m.destination, months=m.months,
                    monthly_income=m.monthly_income,
                ) for m in profile.livelihood_info.migration_patterns
            ],
        ),
        income_records=[
            IncomeRecordDTO(
                month=r.month, year=r.year, amount=r.amount,
                source=r.source, is_verified=r.is_verified,
            ) for r in profile.income_records
        ],
        expense_records=[
            ExpenseRecordDTO(
                month=r.month, year=r.year, amount=r.amount,
                category=r.category,
            ) for r in profile.expense_records
        ],
        seasonal_factors=[
            SeasonalFactorDTO(
                season=f.season.value,
                income_multiplier=f.income_multiplier,
                expense_multiplier=f.expense_multiplier,
                notes=f.notes,
            ) for f in profile.seasonal_factors
        ],
        volatility_metrics=VolatilityMetricsDTO(
            coefficient_of_variation=profile.volatility_metrics.coefficient_of_variation,
            income_range_ratio=profile.volatility_metrics.income_range_ratio,
            seasonal_variance=profile.volatility_metrics.seasonal_variance,
            months_below_average=profile.volatility_metrics.months_below_average,
            volatility_category=profile.volatility_metrics.volatility_category,
        ) if profile.volatility_metrics else None,
        average_monthly_income=profile.get_average_monthly_income(),
        average_monthly_expense=profile.get_average_monthly_expense(),
        monthly_surplus=profile.get_monthly_surplus(),
        estimated_annual_income=profile.estimate_annual_income(),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _to_profile_summary(profile) -> ProfileSummaryDTO:
    return ProfileSummaryDTO(
        profile_id=profile.profile_id,
        name=profile.personal_info.name,
        district=profile.personal_info.district,
        state=profile.personal_info.state,
        primary_occupation=profile.livelihood_info.primary_occupation.value,
        estimated_annual_income=profile.estimate_annual_income(),
        volatility_category=profile.volatility_metrics.volatility_category
        if profile.volatility_metrics else None,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", response_model=ProfileDetailDTO, status_code=201)
def create_profile(
    request: CreateProfileRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Create a new borrower profile."""
    try:
        profile = svc.create_profile(
            personal_info=_to_personal_info(request.personal_info),
            livelihood_info=_to_livelihood_info(request.livelihood_info),
            income_records=_to_income_records(request.income_records),
            expense_records=_to_expense_records(request.expense_records),
            seasonal_factors=_to_seasonal_factors(request.seasonal_factors),
        )
        return _to_profile_detail(profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/{profile_id}", response_model=ProfileDetailDTO)
def get_profile(
    profile_id: str,
    svc: ProfileService = Depends(get_profile_service),
):
    """Get a profile by ID."""
    try:
        profile = svc.get_profile(profile_id)
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None


@router.patch("/{profile_id}/personal-info", response_model=ProfileDetailDTO)
def update_personal_info(
    profile_id: str,
    request: UpdatePersonalInfoRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Update personal info of an existing profile."""
    try:
        profile = svc.update_personal_info(
            profile_id, _to_personal_info(request.personal_info)
        )
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.patch("/{profile_id}/livelihood", response_model=ProfileDetailDTO)
def update_livelihood(
    profile_id: str,
    request: UpdateLivelihoodRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Update livelihood information."""
    try:
        profile = svc.update_livelihood_info(
            profile_id, _to_livelihood_info(request.livelihood_info)
        )
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/{profile_id}/income", response_model=ProfileDetailDTO)
def add_income_records(
    profile_id: str,
    request: AddIncomeRecordsRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Add income records (preserves historical data)."""
    try:
        profile = svc.add_income_records(
            profile_id, _to_income_records(request.records)
        )
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/{profile_id}/expenses", response_model=ProfileDetailDTO)
def add_expense_records(
    profile_id: str,
    request: AddExpenseRecordsRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Add expense records."""
    try:
        profile = svc.add_expense_records(
            profile_id, _to_expense_records(request.records)
        )
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None


@router.put("/{profile_id}/seasonal-factors", response_model=ProfileDetailDTO)
def set_seasonal_factors(
    profile_id: str,
    request: SetSeasonalFactorsRequest,
    svc: ProfileService = Depends(get_profile_service),
):
    """Set seasonal adjustment factors."""
    try:
        profile = svc.set_seasonal_factors(
            profile_id, _to_seasonal_factors(request.factors)
        )
        return _to_profile_detail(profile)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None


@router.get("/{profile_id}/volatility", response_model=VolatilityMetricsDTO)
def get_volatility(
    profile_id: str,
    svc: ProfileService = Depends(get_profile_service),
):
    """Get income volatility metrics."""
    try:
        metrics = svc.get_volatility_metrics(profile_id)
        return VolatilityMetricsDTO(
            coefficient_of_variation=metrics.coefficient_of_variation,
            income_range_ratio=metrics.income_range_ratio,
            seasonal_variance=metrics.seasonal_variance,
            months_below_average=metrics.months_below_average,
            volatility_category=metrics.volatility_category,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("", response_model=PaginatedProfilesDTO)
def list_profiles(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    svc: ProfileService = Depends(get_profile_service),
):
    """List profiles with cursor-based pagination."""
    profiles, next_cursor = svc.list_profiles(limit=limit, cursor=cursor)
    return PaginatedProfilesDTO(
        profiles=[_to_profile_summary(p) for p in profiles],
        next_cursor=next_cursor,
        count=len(profiles),
    )
