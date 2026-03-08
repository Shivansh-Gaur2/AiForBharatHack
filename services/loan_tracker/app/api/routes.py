"""FastAPI routes for the Loan Tracker service.

Translates HTTP requests ↔ domain service calls.
All DTOs live in schemas.py; domain objects are never serialized directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..domain.models import Loan, LoanTerms, RepaymentRecord
from ..domain.services import LoanTrackerService
from .schemas import (
    DebtExposureDTO,
    LoanDetailDTO,
    LoanSummaryDTO,
    LoanTermsDTO,
    PaginatedLoansDTO,
    RecordRepaymentRequest,
    RepaymentRecordDTO,
    SourceExposureDTO,
    TrackLoanRequest,
    UpdateLoanStatusRequest,
)

router = APIRouter(prefix="/api/v1/loans", tags=["Loan Tracker"])

# ---------------------------------------------------------------------------
# Dependency injection (set from main.py)
# ---------------------------------------------------------------------------
_loan_service: LoanTrackerService | None = None


def set_loan_service(svc: LoanTrackerService) -> None:
    global _loan_service
    _loan_service = svc


def get_loan_service() -> LoanTrackerService:
    assert _loan_service is not None, "LoanTrackerService not wired"
    return _loan_service


# ---------------------------------------------------------------------------
# Mappers: Domain ↔ DTO
# ---------------------------------------------------------------------------
def _loan_to_detail(loan: Loan) -> LoanDetailDTO:
    return LoanDetailDTO(
        tracking_id=loan.tracking_id,
        profile_id=loan.profile_id,
        lender_name=loan.lender_name,
        source_type=loan.source_type,
        terms=LoanTermsDTO(
            principal=loan.terms.principal,
            interest_rate_annual=loan.terms.interest_rate_annual,
            tenure_months=loan.terms.tenure_months,
            emi_amount=loan.terms.emi_amount,
            collateral_description=loan.terms.collateral_description,
        ),
        status=loan.status,
        disbursement_date=loan.disbursement_date,
        maturity_date=loan.maturity_date,
        outstanding_balance=loan.outstanding_balance,
        total_repaid=loan.total_repaid,
        repayment_rate=loan.get_repayment_rate(),
        on_time_ratio=loan.get_on_time_ratio(),
        monthly_obligation=loan.get_monthly_obligation(),
        repayment_count=len(loan.repayments),
        repayments=[
            RepaymentRecordDTO(
                date=r.date,
                amount=r.amount,
                is_late=r.is_late,
                days_overdue=r.days_overdue,
            )
            for r in loan.repayments
        ],
        purpose=loan.purpose,
        notes=loan.notes,
        created_at=loan.created_at,
        updated_at=loan.updated_at,
    )


def _loan_to_summary(loan: Loan) -> LoanSummaryDTO:
    return LoanSummaryDTO(
        tracking_id=loan.tracking_id,
        lender_name=loan.lender_name,
        source_type=loan.source_type,
        principal=loan.terms.principal,
        outstanding_balance=loan.outstanding_balance,
        status=loan.status,
        monthly_obligation=loan.get_monthly_obligation(),
    )


@router.get("/stats")
async def get_loan_stats():
    """Aggregate loan statistics for the dashboard."""
    svc = get_loan_service()
    # Scan all loans via repo directly
    repo = svc._repo
    scan_kwargs = {
        "FilterExpression": "begins_with(PK, :pk) AND SK = :sk",
        "ExpressionAttributeValues": {":pk": "LOAN#", ":sk": "METADATA"},
        "Limit": 500,
    }
    response = repo._table.scan(**scan_kwargs)
    items = response.get("Items", [])

    active_count = 0
    total_outstanding = 0.0
    total_disbursed = 0.0
    total_repaid_sum = 0.0
    default_count = 0
    repayment_rates: list[float] = []

    for item in items:
        status = item.get("status", "ACTIVE")
        principal = float(item.get("terms", {}).get("principal", 0))
        outstanding = float(item.get("outstanding_balance", 0))
        total_repaid = float(item.get("total_repaid", 0))

        total_disbursed += principal
        total_outstanding += outstanding
        total_repaid_sum += total_repaid

        if status == "ACTIVE":
            active_count += 1
        elif status == "DEFAULTED":
            default_count += 1

        if principal > 0:
            repayment_rates.append(total_repaid / principal)

    total_loans = len(items)
    avg_repayment_rate = (
        sum(repayment_rates) / len(repayment_rates)
        if repayment_rates
        else 0.0
    )
    default_rate = (
        default_count / total_loans * 100 if total_loans > 0 else 0.0
    )

    return {
        "active_loans": active_count,
        "total_loans": total_loans,
        "total_outstanding": total_outstanding,
        "total_disbursed": total_disbursed,
        "avg_repayment_rate": round(avg_repayment_rate * 100, 1),
        "default_count": default_count,
        "default_rate": round(default_rate, 1),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", response_model=LoanDetailDTO, status_code=201)
async def track_loan(req: TrackLoanRequest):
    """Register a new loan for tracking."""
    svc = get_loan_service()
    try:
        loan = await svc.track_loan(
            profile_id=req.profile_id,
            lender_name=req.lender_name,
            source_type=req.source_type,
            terms=LoanTerms(
                principal=req.terms.principal,
                interest_rate_annual=req.terms.interest_rate_annual,
                tenure_months=req.terms.tenure_months,
                emi_amount=req.terms.emi_amount,
                collateral_description=req.terms.collateral_description,
            ),
            disbursement_date=req.disbursement_date,
            maturity_date=req.maturity_date,
            purpose=req.purpose,
            notes=req.notes,
        )
        return _loan_to_detail(loan)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/{tracking_id}", response_model=LoanDetailDTO)
async def get_loan(tracking_id: str):
    """Get details of a tracked loan."""
    svc = get_loan_service()
    loan = await svc.get_loan(tracking_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    return _loan_to_detail(loan)


@router.post("/{tracking_id}/repayments", response_model=LoanDetailDTO)
async def record_repayment(tracking_id: str, req: RecordRepaymentRequest):
    """Record a repayment against a loan."""
    svc = get_loan_service()
    try:
        repayment = RepaymentRecord(
            date=req.date,
            amount=req.amount,
            is_late=req.is_late,
            days_overdue=req.days_overdue,
        )
        loan = await svc.record_repayment(tracking_id, repayment)
        return _loan_to_detail(loan)
    except KeyError:
        raise HTTPException(status_code=404, detail="Loan not found") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.patch("/{tracking_id}/status", response_model=LoanDetailDTO)
async def update_status(tracking_id: str, req: UpdateLoanStatusRequest):
    """Update loan status (ACTIVE, CLOSED, DEFAULTED, RESTRUCTURED)."""
    svc = get_loan_service()
    try:
        loan = await svc.update_loan_status(tracking_id, req.status)
        return _loan_to_detail(loan)
    except KeyError:
        raise HTTPException(status_code=404, detail="Loan not found") from None


@router.get("/borrower/{profile_id}", response_model=PaginatedLoansDTO)
async def get_borrower_loans(
    profile_id: str,
    active_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
):
    """List all loans for a borrower."""
    svc = get_loan_service()
    loans, next_cursor = await svc.get_borrower_loans(
        profile_id, active_only=active_only, limit=limit, cursor=cursor,
    )
    return PaginatedLoansDTO(
        items=[_loan_to_summary(l) for l in loans],
        next_cursor=next_cursor,
        count=len(loans),
    )


@router.get("/borrower/{profile_id}/exposure", response_model=DebtExposureDTO)
async def get_exposure(
    profile_id: str,
    annual_income: float = Query(gt=0),
):
    """Get aggregate debt exposure for a borrower (Property 4)."""
    svc = get_loan_service()
    exposure = await svc.get_total_exposure(profile_id, annual_income)
    return DebtExposureDTO(
        profile_id=exposure.profile_id,
        total_outstanding=exposure.total_outstanding,
        monthly_obligations=exposure.monthly_obligations,
        debt_to_income_ratio=exposure.debt_to_income_ratio,
        credit_utilisation=exposure.credit_utilisation,
        by_source=[
            SourceExposureDTO(
                source_type=se.source_type,
                total_outstanding=se.total_outstanding,
                loan_count=se.loan_count,
                weighted_avg_interest=se.weighted_avg_interest,
            )
            for se in exposure.by_source
        ],
        active_loan_count=exposure.active_loan_count,
        total_loan_count=exposure.total_loan_count,
        computed_at=exposure.computed_at,
    )


@router.delete("/borrower/{profile_id}", status_code=204)
async def delete_borrower_loans(profile_id: str):
    """Delete all loan records for a borrower (cascade on profile deletion)."""
    svc = get_loan_service()
    await svc.delete_profile_data(profile_id)
