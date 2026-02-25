"""Domain validators for loan data.

Enforces rural-context business rules for loan tracking.
Uses shared validation constants.
"""

from __future__ import annotations

from datetime import UTC, datetime

from services.shared.validation import (
    MAX_LOAN_TENURE_MONTHS,
    ValidationError,
    ValidationResult,
    validate_interest_rate,
    validate_loan_amount,
)

from .models import Loan, LoanTerms, RepaymentRecord


def validate_loan_terms(terms: LoanTerms) -> ValidationResult:
    """Validate the terms of a loan against rural-context constraints."""
    errors: list[ValidationError] = []

    # Principal
    err = validate_loan_amount(terms.principal)
    if err:
        errors.append(ValidationError(
            field="principal", message=err.message, value=err.value,
        ))

    # Interest rate
    err = validate_interest_rate(terms.interest_rate_annual)
    if err:
        errors.append(err)

    # Tenure
    if terms.tenure_months <= 0:
        errors.append(ValidationError(
            field="tenure_months",
            message="Loan tenure must be positive",
            value=terms.tenure_months,
        ))
    elif terms.tenure_months > MAX_LOAN_TENURE_MONTHS:
        errors.append(ValidationError(
            field="tenure_months",
            message=f"Tenure {terms.tenure_months} months exceeds maximum {MAX_LOAN_TENURE_MONTHS}",
            value=terms.tenure_months,
        ))

    # EMI cannot be negative
    if terms.emi_amount < 0:
        errors.append(ValidationError(
            field="emi_amount",
            message="EMI amount cannot be negative",
            value=terms.emi_amount,
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_loan_creation(
    lender_name: str,
    terms: LoanTerms,
    disbursement_date: datetime,
) -> ValidationResult:
    """Full validation for creating a new loan."""
    errors: list[ValidationError] = []

    # Lender name required
    if not lender_name or not lender_name.strip():
        errors.append(ValidationError(
            field="lender_name",
            message="Lender name is required",
            value=lender_name,
        ))

    # Terms validation
    terms_result = validate_loan_terms(terms)
    if not terms_result.is_valid:
        errors.extend(terms_result.errors)

    # Disbursement date cannot be in the far future (1 year tolerance)
    now = datetime.now(UTC)
    # Ensure both datetimes are timezone-aware for comparison
    disb = disbursement_date
    if disb.tzinfo is None:
        disb = disb.replace(tzinfo=UTC)
    days_ahead = (disb - now).days
    if days_ahead > 365:
        errors.append(ValidationError(
            field="disbursement_date",
            message="Disbursement date is more than 1 year in the future",
            value=str(disbursement_date),
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_repayment(
    repayment: RepaymentRecord,
    loan: Loan,
) -> ValidationResult:
    """Validate a repayment record against the loan state."""
    errors: list[ValidationError] = []

    if repayment.amount <= 0:
        errors.append(ValidationError(
            field="repayment_amount",
            message="Repayment amount must be positive",
            value=repayment.amount,
        ))

    if repayment.amount > loan.outstanding_balance * 1.1:
        # Allow 10% overpayment (fees/penalties) but flag extreme values
        errors.append(ValidationError(
            field="repayment_amount",
            message=f"Repayment ₹{repayment.amount:,.0f} significantly exceeds outstanding ₹{loan.outstanding_balance:,.0f}",
            value=repayment.amount,
        ))

    if repayment.days_overdue < 0:
        errors.append(ValidationError(
            field="days_overdue",
            message="Days overdue cannot be negative",
            value=repayment.days_overdue,
        ))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)
