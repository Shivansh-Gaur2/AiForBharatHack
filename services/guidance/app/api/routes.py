"""FastAPI routes for the Guidance Service.

Translates HTTP requests <-> domain service calls.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..domain.models import CreditGuidance
from ..domain.services import GuidanceService
from .schemas import (
    AlternativeOptionDTO,
    AmountDTO,
    AmountRangeDTO,
    AmountRequest,
    DirectGuidanceRequest,
    GuidanceDTO,
    GuidanceExplanationDTO,
    GuidanceListDTO,
    GuidanceRequest,
    GuidanceSummaryDTO,
    ReasoningStepDTO,
    RiskSummaryDTO,
    SuggestedTermsDTO,
    TimingDTO,
    TimingRequest,
    TimingWindowDTO,
)

router = APIRouter(prefix="/api/v1/guidance", tags=["Guidance"])

# ---------------------------------------------------------------------------
# Service injection (set from main.py)
# ---------------------------------------------------------------------------
_guidance_service: GuidanceService | None = None


def set_guidance_service(svc: GuidanceService) -> None:
    global _guidance_service
    _guidance_service = svc


def get_guidance_service() -> GuidanceService:
    if _guidance_service is None:
        raise RuntimeError("GuidanceService not initialised")
    return _guidance_service


# ---------------------------------------------------------------------------
# DTO converters
# ---------------------------------------------------------------------------


def _guidance_to_dto(g: CreditGuidance) -> GuidanceDTO:
    return GuidanceDTO(
        guidance_id=g.guidance_id,
        profile_id=g.profile_id,
        loan_purpose=g.loan_purpose,
        requested_amount=g.requested_amount,
        recommended_amount=AmountRangeDTO(
            min_amount=g.recommended_amount.min_amount,
            max_amount=g.recommended_amount.max_amount,
            currency=g.recommended_amount.currency,
        ),
        optimal_timing=TimingWindowDTO(
            start_month=g.optimal_timing.start_month,
            start_year=g.optimal_timing.start_year,
            end_month=g.optimal_timing.end_month,
            end_year=g.optimal_timing.end_year,
            suitability=g.optimal_timing.suitability,
            reason=g.optimal_timing.reason,
            expected_surplus=g.optimal_timing.expected_surplus,
        ),
        suggested_terms=SuggestedTermsDTO(
            tenure_months=g.suggested_terms.tenure_months,
            interest_rate_max_pct=g.suggested_terms.interest_rate_max_pct,
            emi_amount=g.suggested_terms.emi_amount,
            total_repayment=g.suggested_terms.total_repayment,
            source_recommendation=g.suggested_terms.source_recommendation,
        ),
        risk_summary=RiskSummaryDTO(
            risk_category=g.risk_summary.risk_category,
            risk_score=g.risk_summary.risk_score,
            dti_ratio=g.risk_summary.dti_ratio,
            repayment_capacity_pct=g.risk_summary.repayment_capacity_pct,
            key_risk_factors=g.risk_summary.key_risk_factors,
        ),
        alternative_options=[
            AlternativeOptionDTO(
                option_type=o.option_type,
                description=o.description,
                estimated_amount=o.estimated_amount,
                advantages=o.advantages,
                disadvantages=o.disadvantages,
            )
            for o in g.alternative_options
        ],
        explanation=GuidanceExplanationDTO(
            summary=g.explanation.summary,
            reasoning_steps=[
                ReasoningStepDTO(
                    step_number=s.step_number,
                    factor=s.factor,
                    observation=s.observation,
                    impact=s.impact,
                )
                for s in g.explanation.reasoning_steps
            ],
            confidence=g.explanation.confidence,
            caveats=g.explanation.caveats,
        ),
        status=g.status,
        created_at=g.created_at,
        expires_at=g.expires_at,
    )


def _guidance_to_summary(g: CreditGuidance) -> GuidanceSummaryDTO:
    return GuidanceSummaryDTO(
        guidance_id=g.guidance_id,
        profile_id=g.profile_id,
        loan_purpose=g.loan_purpose,
        recommended_max=g.recommended_amount.max_amount,
        risk_category=g.risk_summary.risk_category,
        status=g.status,
        created_at=g.created_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats")
async def get_guidance_stats():
    """Aggregate guidance statistics for the dashboard."""
    svc = get_guidance_service()
    repo = svc._repo
    scan_kwargs = {
        "FilterExpression": "begins_with(PK, :pk) AND SK = :sk",
        "ExpressionAttributeValues": {":pk": "GUIDANCE#", ":sk": "METADATA"},
        "Limit": 500,
    }
    response = repo._table.scan(**scan_kwargs)
    items = response.get("Items", [])

    total = len(items)
    active = sum(1 for i in items if i.get("status") == "ACTIVE")

    return {
        "total_issued": total,
        "active_count": active,
    }


@router.post("/generate", response_model=GuidanceDTO, status_code=201)
async def generate_guidance(req: GuidanceRequest):
    """Generate personalized credit guidance (Req 7.1) — cross-service."""
    svc = get_guidance_service()
    try:
        guidance = await svc.generate_guidance(
            profile_id=req.profile_id,
            loan_purpose=req.loan_purpose,
            requested_amount=req.requested_amount,
            tenure_months=req.tenure_months,
            interest_rate_annual=req.interest_rate_annual,
        )
        return _guidance_to_dto(guidance)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/generate/direct", response_model=GuidanceDTO, status_code=201)
async def generate_guidance_direct(req: DirectGuidanceRequest):
    """Generate guidance from directly-provided data."""
    svc = get_guidance_service()
    try:
        projections = [(p.month, p.year, p.inflow, p.outflow) for p in req.projections]
        guidance = await svc.generate_guidance_direct(
            profile_id=req.profile_id,
            loan_purpose=req.loan_purpose,
            projections=projections,
            risk_category=req.risk_category,
            risk_score=req.risk_score,
            dti_ratio=req.dti_ratio,
            existing_obligations=req.existing_obligations,
            requested_amount=req.requested_amount,
            tenure_months=req.tenure_months,
            interest_rate_annual=req.interest_rate_annual,
        )
        return _guidance_to_dto(guidance)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/timing", response_model=TimingDTO)
async def optimize_timing(req: TimingRequest):
    """Get optimal loan timing (Req 7.2) — cross-service."""
    svc = get_guidance_service()
    try:
        timing = await svc.get_optimal_timing(
            profile_id=req.profile_id,
            loan_amount=req.loan_amount,
            tenure_months=req.tenure_months,
        )
        return TimingDTO(
            profile_id=req.profile_id,
            timing=TimingWindowDTO(
                start_month=timing.start_month,
                start_year=timing.start_year,
                end_month=timing.end_month,
                end_year=timing.end_year,
                suitability=timing.suitability,
                reason=timing.reason,
                expected_surplus=timing.expected_surplus,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/amount", response_model=AmountDTO)
async def recommend_amount(req: AmountRequest):
    """Get recommended loan amount (Req 7.3) — cross-service."""
    svc = get_guidance_service()
    try:
        amount = await svc.get_recommended_amount(
            profile_id=req.profile_id,
            tenure_months=req.tenure_months,
            interest_rate_annual=req.interest_rate_annual,
        )
        return AmountDTO(
            profile_id=req.profile_id,
            recommended_amount=AmountRangeDTO(
                min_amount=amount.min_amount,
                max_amount=amount.max_amount,
                currency=amount.currency,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/profile/{profile_id}/history")
async def get_guidance_history(
    profile_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get guidance history for a profile."""
    svc = get_guidance_service()
    items = await svc.get_guidance_history(profile_id, limit)
    return {
        "items": [_guidance_to_dto(g) for g in items],
        "count": len(items),
    }


@router.get("/profile/{profile_id}/active")
async def get_active_guidance(profile_id: str):
    """Get active (non-expired) guidance for a profile."""
    svc = get_guidance_service()
    items = await svc.get_active_guidance(profile_id)
    return {
        "items": [_guidance_to_dto(g) for g in items],
        "count": len(items),
    }


@router.get("/{guidance_id}", response_model=GuidanceDTO)
async def get_guidance(guidance_id: str):
    """Get a specific guidance record."""
    svc = get_guidance_service()
    guidance = await svc.get_guidance(guidance_id)
    if guidance is None:
        raise HTTPException(status_code=404, detail="Guidance not found")
    return _guidance_to_dto(guidance)


@router.get("/{guidance_id}/explain", response_model=GuidanceExplanationDTO)
async def explain_guidance(guidance_id: str):
    """Get human-readable explanation for guidance (Req 7.5)."""
    svc = get_guidance_service()
    guidance = await svc.get_guidance(guidance_id)
    if guidance is None:
        raise HTTPException(status_code=404, detail="Guidance not found")
    return GuidanceExplanationDTO(
        summary=guidance.explanation.summary,
        reasoning_steps=[
            ReasoningStepDTO(
                step_number=s.step_number,
                factor=s.factor,
                observation=s.observation,
                impact=s.impact,
            )
            for s in guidance.explanation.reasoning_steps
        ],
        confidence=guidance.explanation.confidence,
        caveats=guidance.explanation.caveats,
    )


@router.post("/{guidance_id}/supersede", response_model=GuidanceDTO)
async def supersede_guidance(guidance_id: str):
    """Mark guidance as superseded by newer guidance."""
    svc = get_guidance_service()
    try:
        guidance = await svc.supersede_guidance(guidance_id)
        return _guidance_to_dto(guidance)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.post("/{guidance_id}/expire", response_model=GuidanceDTO)
async def expire_guidance(guidance_id: str):
    """Mark guidance as expired."""
    svc = get_guidance_service()
    try:
        guidance = await svc.expire_guidance(guidance_id)
        return _guidance_to_dto(guidance)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
