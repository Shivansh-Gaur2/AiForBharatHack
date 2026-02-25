"""FastAPI routes for the Risk Assessment service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..domain.models import RiskAssessment, RiskInput
from ..domain.services import RiskAssessmentService
from .schemas import (
    AssessRiskRequest,
    DirectRiskInput,
    RiskAssessmentDTO,
    RiskExplainDTO,
    RiskExplanationDTO,
    RiskFactorDTO,
    RiskSummaryDTO,
)

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Assessment"])

# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------
_risk_service: RiskAssessmentService | None = None


def set_risk_service(svc: RiskAssessmentService) -> None:
    global _risk_service
    _risk_service = svc


def get_risk_service() -> RiskAssessmentService:
    assert _risk_service is not None, "RiskAssessmentService not wired"
    return _risk_service


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------
def _assessment_to_dto(a: RiskAssessment) -> RiskAssessmentDTO:
    return RiskAssessmentDTO(
        assessment_id=a.assessment_id,
        profile_id=a.profile_id,
        risk_score=a.risk_score,
        risk_category=a.risk_category,
        confidence_level=a.confidence_level,
        factors=[
            RiskFactorDTO(
                factor_type=f.factor_type.value,
                score=f.score,
                weight=f.weight,
                description=f.description,
                data_points=f.data_points,
            )
            for f in a.factors
        ],
        explanation=RiskExplanationDTO(
            summary=a.explanation.summary,
            key_factors=a.explanation.key_factors,
            recommendations=a.explanation.recommendations,
            confidence_note=a.explanation.confidence_note,
        ),
        valid_until=a.valid_until,
        model_version=a.model_version,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/assess", response_model=RiskAssessmentDTO, status_code=201)
async def assess_risk(req: AssessRiskRequest):
    """Run a full risk assessment for a borrower (cross-service data)."""
    svc = get_risk_service()
    try:
        assessment = await svc.assess_risk(req.profile_id)
        return _assessment_to_dto(assessment)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/score", response_model=RiskAssessmentDTO, status_code=201)
async def score_direct(req: DirectRiskInput):
    """Score with explicit inputs (no cross-service calls)."""
    svc = get_risk_service()
    risk_input = RiskInput(
        profile_id=req.profile_id,
        income_volatility_cv=req.income_volatility_cv,
        annual_income=req.annual_income,
        months_below_average=req.months_below_average,
        debt_to_income_ratio=req.debt_to_income_ratio,
        total_outstanding=req.total_outstanding,
        active_loan_count=req.active_loan_count,
        credit_utilisation=req.credit_utilisation,
        on_time_repayment_ratio=req.on_time_repayment_ratio,
        has_defaults=req.has_defaults,
        seasonal_variance=req.seasonal_variance,
        crop_diversification_index=req.crop_diversification_index,
        weather_risk_score=req.weather_risk_score,
        market_risk_score=req.market_risk_score,
        dependents=req.dependents,
        age=req.age,
        has_irrigation=req.has_irrigation,
    )
    assessment = await svc.assess_risk_with_input(risk_input)
    return _assessment_to_dto(assessment)


@router.get("/profile/{profile_id}", response_model=RiskAssessmentDTO)
async def get_latest(profile_id: str):
    """Get the latest risk assessment for a profile."""
    svc = get_risk_service()
    assessment = await svc.get_latest_assessment(profile_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="No assessment found")
    return _assessment_to_dto(assessment)


@router.get("/profile/{profile_id}/history", response_model=list[RiskSummaryDTO])
async def get_history(
    profile_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """Get risk assessment history for a profile."""
    svc = get_risk_service()
    assessments = await svc.get_assessment_history(profile_id, limit=limit)
    return [
        RiskSummaryDTO(
            assessment_id=a.assessment_id,
            profile_id=a.profile_id,
            risk_score=a.risk_score,
            risk_category=a.risk_category,
            confidence_level=a.confidence_level,
            created_at=a.created_at,
        )
        for a in assessments
    ]


@router.get("/{assessment_id}", response_model=RiskAssessmentDTO)
async def get_assessment(assessment_id: str):
    """Get a specific risk assessment by ID."""
    svc = get_risk_service()
    assessment = await svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _assessment_to_dto(assessment)


@router.get("/{assessment_id}/explain", response_model=RiskExplainDTO)
async def explain_risk(assessment_id: str):
    """Get a simplified human-readable risk explanation."""
    svc = get_risk_service()
    explanation = await svc.explain_risk(assessment_id)
    if explanation is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return RiskExplainDTO(**explanation)
