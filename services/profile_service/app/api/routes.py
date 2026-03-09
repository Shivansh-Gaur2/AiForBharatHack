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

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from services.profile_service.app.domain.models import (
    BusinessDetails,
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
        location=dto.location,
    )


def _to_livelihood_info(dto) -> LivelihoodInfo:
    land = None
    ld = dto.land_details
    if ld is not None:
        total = ld.owned_acres + ld.leased_acres
        irrigated = total * ld.irrigated_percentage / 100.0 if total > 0 else 0.0
        land = LandDetails(
            total_acres=total,
            irrigated_acres=round(irrigated, 2),
            rain_fed_acres=round(total - irrigated, 2),
            ownership_type="OWNED" if ld.leased_acres == 0 else "LEASED",
        )
    biz = None
    if dto.business_details is not None:
        b = dto.business_details
        biz = BusinessDetails(
            business_type=b.business_type,
            workspace_owned=b.workspace_owned,
            workspace_description=b.workspace_description,
            monthly_revenue=b.monthly_revenue,
            monthly_expenses=b.monthly_expenses,
            investment_amount=b.investment_amount,
            years_in_business=b.years_in_business,
        )
    return LivelihoodInfo(
        primary_occupation=OccupationType(dto.primary_occupation),
        secondary_occupations=[OccupationType(o) for o in dto.secondary_occupations],
        land_holding=land,
        crop_patterns=[
            CropInfo(
                crop_name=c.crop_name,
                season=Season(c.season),
                area_acres=c.area_acres,
                expected_yield_quintals=c.expected_yield_quintals,
                expected_price_per_quintal=c.expected_price_per_quintal,
            ) for c in dto.crops
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
                months=list(range(1, m.duration_months + 1)) if m.duration_months else [],
                monthly_income=m.monthly_income,
            ) for m in dto.migration_patterns
        ],
        business_details=biz,
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
            notes=f.description,
        ) for f in dtos
    ]


# ---------------------------------------------------------------------------
# Domain → Response DTO mappers
# ---------------------------------------------------------------------------
def _to_profile_detail(profile) -> ProfileDetailDTO:
    from .schemas import (
        BusinessDetailsDTO,
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
            location=getattr(profile.personal_info, 'location', ''),
            district=profile.personal_info.district,
            state=profile.personal_info.state,
            dependents=profile.personal_info.dependents,
            phone=profile.personal_info.phone,
        ),
        livelihood_info=LivelihoodInfoDTO(
            primary_occupation=profile.livelihood_info.primary_occupation.value,
            secondary_occupations=[o.value for o in profile.livelihood_info.secondary_occupations],
            land_details=LandDetailsDTO(
                owned_acres=profile.livelihood_info.land_holding.total_acres,
                leased_acres=0,
                irrigated_percentage=round(
                    profile.livelihood_info.land_holding.irrigated_acres
                    / profile.livelihood_info.land_holding.total_acres * 100, 1
                ) if profile.livelihood_info.land_holding.total_acres > 0 else 0,
            ) if profile.livelihood_info.land_holding else None,
            crops=[
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
                    destination=m.destination, duration_months=len(m.months),
                    monthly_income=m.monthly_income,
                    season="KHARIF",
                ) for m in profile.livelihood_info.migration_patterns
            ],
            business_details=BusinessDetailsDTO(
                business_type=profile.livelihood_info.business_details.business_type,
                workspace_owned=profile.livelihood_info.business_details.workspace_owned,
                workspace_description=profile.livelihood_info.business_details.workspace_description,
                monthly_revenue=profile.livelihood_info.business_details.monthly_revenue,
                monthly_expenses=profile.livelihood_info.business_details.monthly_expenses,
                investment_amount=profile.livelihood_info.business_details.investment_amount,
                years_in_business=profile.livelihood_info.business_details.years_in_business,
            ) if profile.livelihood_info.business_details else None,
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
                description=f.notes,
            ) for f in profile.seasonal_factors
        ],
        volatility_metrics=VolatilityMetricsDTO(
            coefficient_of_variation=profile.volatility_metrics.coefficient_of_variation,
            income_range_ratio=profile.volatility_metrics.income_range_ratio,
            seasonal_variance=profile.volatility_metrics.seasonal_variance,
            months_below_average=profile.volatility_metrics.months_below_average,
            volatility_level=profile.volatility_metrics.volatility_category,
        ) if profile.volatility_metrics else None,
        average_monthly_income=profile.get_average_monthly_income(),
        average_monthly_expense=profile.get_average_monthly_expense(),
        monthly_surplus=profile.get_monthly_surplus(),
        estimated_annual_income=profile.estimate_annual_income(),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _to_profile_summary(profile) -> ProfileSummaryDTO:
    loc = getattr(profile.personal_info, 'location', '') or ''
    if not loc:
        loc = f"{profile.personal_info.district}, {profile.personal_info.state}"
    return ProfileSummaryDTO(
        profile_id=profile.profile_id,
        name=profile.personal_info.name,
        location=loc,
        occupation=profile.livelihood_info.primary_occupation.value,
        volatility_level=profile.volatility_metrics.volatility_category
        if profile.volatility_metrics else None,
        created_at=profile.created_at.isoformat() if hasattr(profile.created_at, 'isoformat') else str(profile.created_at),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/stats")
def get_profile_stats(
    svc: ProfileService = Depends(get_profile_service),
):
    """Aggregate profile statistics for the dashboard."""
    from datetime import datetime, timedelta, timezone

    profiles, _ = svc.list_profiles(limit=500)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    total = len(profiles)
    recent = sum(
        1 for p in profiles
        if hasattr(p, "created_at") and p.created_at and p.created_at >= thirty_days_ago
    )

    # Occupation breakdown
    occupations: dict[str, int] = {}
    for p in profiles:
        occ = p.livelihood_info.primary_occupation.value
        occupations[occ] = occupations.get(occ, 0) + 1

    return {
        "total_profiles": total,
        "recent_count": recent,
        "occupation_breakdown": occupations,
    }


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
            volatility_level=metrics.volatility_category,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


async def _cascade_delete_profile(profile_id: str) -> None:
    """Best-effort cascade: delete all data for this profile across every service.

    Failures are logged but never surface as errors — the profile is already
    gone; we don't want to block the 204 response on downstream availability.
    """
    cascade_urls = [
        f"http://127.0.0.1:8002/api/v1/loans/borrower/{profile_id}",
        f"http://127.0.0.1:8003/api/v1/risk/profile/{profile_id}",
        f"http://127.0.0.1:8004/api/v1/cashflow/profile/{profile_id}",
        f"http://127.0.0.1:8005/api/v1/early-warning/profile/{profile_id}",
        f"http://127.0.0.1:8006/api/v1/guidance/profile/{profile_id}",
        f"http://127.0.0.1:8007/api/v1/security/profile/{profile_id}",
    ]
    async with httpx.AsyncClient(timeout=5.0) as client:
        results = await asyncio.gather(
            *[client.delete(url) for url in cascade_urls],
            return_exceptions=True,
        )
    for url, result in zip(cascade_urls, results):
        if isinstance(result, Exception):
            logger.warning("Cascade delete failed for %s: %s", url, result)
        elif result.status_code not in (200, 204):
            logger.warning("Cascade delete returned %s for %s", result.status_code, url)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    svc: ProfileService = Depends(get_profile_service),
):
    """Permanently delete a borrower profile and cascade to all related services."""
    try:
        svc.delete_profile(profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from None
    await _cascade_delete_profile(profile_id)


@router.get("", response_model=PaginatedProfilesDTO)
def list_profiles(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    svc: ProfileService = Depends(get_profile_service),
):
    """List profiles with cursor-based pagination."""
    profiles, next_cursor = svc.list_profiles(limit=limit, cursor=cursor)
    return PaginatedProfilesDTO(
        items=[_to_profile_summary(p) for p in profiles],
        cursor=next_cursor,
        has_more=next_cursor is not None,
    )
