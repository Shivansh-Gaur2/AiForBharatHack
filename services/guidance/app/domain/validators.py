"""Input validators for the Guidance Service.

Pure validation — no side effects, no I/O.
"""

from __future__ import annotations

from .models import LoanPurpose


def validate_guidance_request(
    profile_id: str,
    loan_purpose: str,
    requested_amount: float | None = None,
    tenure_months: int | None = None,
    interest_rate_annual: float | None = None,
) -> None:
    """Validate a full credit guidance request."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must not be empty")

    # Validate purpose
    valid_purposes = {p.value for p in LoanPurpose}
    if loan_purpose not in valid_purposes:
        raise ValueError(
            f"Invalid loan_purpose '{loan_purpose}'. "
            f"Must be one of: {', '.join(sorted(valid_purposes))}"
        )

    if requested_amount is not None:
        if requested_amount < 0:
            raise ValueError("requested_amount must be non-negative")
        if requested_amount > 10_000_000:
            raise ValueError("requested_amount exceeds maximum (1 crore)")

    if tenure_months is not None:
        if tenure_months < 1:
            raise ValueError("tenure_months must be at least 1")
        if tenure_months > 120:
            raise ValueError("tenure_months must not exceed 120 (10 years)")

    if interest_rate_annual is not None:
        if interest_rate_annual < 0:
            raise ValueError("interest_rate_annual must be non-negative")
        if interest_rate_annual > 50:
            raise ValueError("interest_rate_annual must not exceed 50%")


def validate_timing_request(
    profile_id: str,
    loan_amount: float,
    tenure_months: int | None = None,
) -> None:
    """Validate a timing-only request."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must not be empty")

    if loan_amount <= 0:
        raise ValueError("loan_amount must be positive")
    if loan_amount > 10_000_000:
        raise ValueError("loan_amount exceeds maximum (1 crore)")

    if tenure_months is not None:
        if tenure_months < 1:
            raise ValueError("tenure_months must be at least 1")
        if tenure_months > 120:
            raise ValueError("tenure_months must not exceed 120")


def validate_amount_request(
    profile_id: str,
    tenure_months: int | None = None,
    interest_rate_annual: float | None = None,
) -> None:
    """Validate an amount-only request."""
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must not be empty")

    if tenure_months is not None:
        if tenure_months < 1:
            raise ValueError("tenure_months must be at least 1")
        if tenure_months > 120:
            raise ValueError("tenure_months must not exceed 120")

    if interest_rate_annual is not None:
        if interest_rate_annual < 0:
            raise ValueError("interest_rate_annual must be non-negative")
        if interest_rate_annual > 50:
            raise ValueError("interest_rate_annual must not exceed 50%")


def validate_direct_guidance_request(
    profile_id: str,
    loan_purpose: str,
    projections: list[tuple[int, int, float, float]],
    risk_category: str,
    risk_score: float,
    dti_ratio: float,
    existing_obligations: float,
) -> None:
    """Validate a direct guidance request (no cross-service calls)."""
    validate_guidance_request(profile_id, loan_purpose)

    if not projections:
        raise ValueError("projections must not be empty")
    if len(projections) > 60:
        raise ValueError("projections must not exceed 60 months")

    for month, year, inflow, outflow in projections:
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month: {month}")
        if year < 2020 or year > 2035:
            raise ValueError(f"Invalid year: {year}")
        if inflow < 0:
            raise ValueError("Inflow must be non-negative")
        if outflow < 0:
            raise ValueError("Outflow must be non-negative")

    from services.shared.models import RiskCategory
    valid_categories = {c.value for c in RiskCategory}
    if risk_category not in valid_categories:
        raise ValueError(
            f"Invalid risk_category '{risk_category}'. "
            f"Must be one of: {', '.join(sorted(valid_categories))}"
        )

    if risk_score < 0 or risk_score > 1000:
        raise ValueError("risk_score must be between 0 and 1000")

    if dti_ratio < 0 or dti_ratio > 5.0:
        raise ValueError("dti_ratio must be between 0 and 5.0")

    if existing_obligations < 0:
        raise ValueError("existing_obligations must be non-negative")
