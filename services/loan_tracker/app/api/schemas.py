"""Pydantic DTOs for the Loan Tracker API.

These are the interface-layer data-transfer objects.
They handle serialization/validation at the HTTP boundary.
Domain models are never exposed directly to clients.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from services.shared.models import LoanSourceType, LoanStatus


# ---------------------------------------------------------------------------
# Nested DTOs
# ---------------------------------------------------------------------------
class LoanTermsDTO(BaseModel):
    principal: float = Field(gt=0, description="Loan principal in INR")
    interest_rate_annual: float = Field(ge=0, le=60, description="Annual interest rate %")
    tenure_months: int = Field(gt=0, le=240, description="Loan tenure in months")
    emi_amount: float = Field(ge=0, description="Monthly EMI (0 for bullet repayment)")
    collateral_description: str | None = None


class RepaymentDTO(BaseModel):
    date: datetime
    amount: float = Field(gt=0)
    is_late: bool = False
    days_overdue: int = Field(ge=0, default=0)


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------
class TrackLoanRequest(BaseModel):
    profile_id: str
    lender_name: str = Field(min_length=1, max_length=200)
    source_type: LoanSourceType
    terms: LoanTermsDTO
    disbursement_date: datetime
    maturity_date: datetime | None = None
    purpose: str = ""
    notes: str = ""


class RecordRepaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    principal_component: float = Field(ge=0, default=0.0)
    interest_component: float = Field(ge=0, default=0.0)
    penalty: float = Field(ge=0, default=0.0)
    repayment_date: str | None = None  # ISO date string; defaults to today


class UpdateLoanStatusRequest(BaseModel):
    status: LoanStatus
    reason: str | None = None


class GetExposureRequest(BaseModel):
    annual_income: float = Field(gt=0, description="Borrower annual income for DTI calculation")


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------
class RepaymentRecordDTO(BaseModel):
    repayment_date: str
    amount: float
    principal_component: float
    interest_component: float
    penalty: float


class LoanDetailDTO(BaseModel):
    tracking_id: str
    profile_id: str
    lender_name: str
    source_type: LoanSourceType
    terms: LoanTermsDTO
    status: LoanStatus
    disbursement_date: datetime
    maturity_date: datetime | None
    outstanding_balance: float
    total_repaid: float
    repayment_rate: float
    on_time_ratio: float
    monthly_obligation: float
    repayment_count: int
    repayments: list[RepaymentRecordDTO] = []
    purpose: str
    notes: str
    created_at: datetime
    updated_at: datetime


class LoanSummaryDTO(BaseModel):
    tracking_id: str
    lender_name: str
    source_type: LoanSourceType
    principal: float
    outstanding_balance: float
    status: LoanStatus
    monthly_obligation: float


class SourceExposureDTO(BaseModel):
    source_type: LoanSourceType
    total_outstanding: float
    loan_count: int
    weighted_avg_interest: float
    monthly_obligation: float = 0.0


class DebtExposureDTO(BaseModel):
    profile_id: str
    total_outstanding: float
    monthly_obligations: float
    debt_to_income_ratio: float
    credit_utilisation: float
    by_source: list[SourceExposureDTO]
    active_loan_count: int
    total_loan_count: int
    assessed_at: datetime


class PaginatedLoansDTO(BaseModel):
    items: list[LoanSummaryDTO]
    next_cursor: str | None = None
    count: int


class ErrorDTO(BaseModel):
    detail: str
