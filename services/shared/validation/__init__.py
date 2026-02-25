"""Common validators for rural financial data.

These enforce reasonable ranges and constraints for Indian rural contexts.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------
@dataclass
class ValidationError:
    field: str
    message: str
    value: object = None


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError]

    @staticmethod
    def ok() -> ValidationResult:
        return ValidationResult(is_valid=True, errors=[])

    @staticmethod
    def fail(errors: list[ValidationError]) -> ValidationResult:
        return ValidationResult(is_valid=False, errors=errors)

    def merge(self, other: ValidationResult) -> ValidationResult:
        combined = self.errors + other.errors
        return ValidationResult(is_valid=len(combined) == 0, errors=combined)


# ---------------------------------------------------------------------------
# Rural-context range constants (INR)
# ---------------------------------------------------------------------------
MIN_ANNUAL_INCOME = 5_000         # ₹5,000   — survival floor
MAX_ANNUAL_INCOME = 25_00_000     # ₹25 lakh — upper bound for rural
MIN_LOAN_AMOUNT = 500             # ₹500
MAX_LOAN_AMOUNT = 50_00_000       # ₹50 lakh
MIN_LAND_HOLDING_ACRES = 0.0
MAX_LAND_HOLDING_ACRES = 100.0
MAX_INTEREST_RATE = 60.0          # 60% — covers informal lending
MIN_INTEREST_RATE = 0.0
MAX_LOAN_TENURE_MONTHS = 240      # 20 years
MAX_DEPENDENTS = 20


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------
def validate_income(annual_income: float) -> ValidationError | None:
    if annual_income < MIN_ANNUAL_INCOME:
        return ValidationError(
            field="annual_income",
            message=f"Annual income ₹{annual_income:,.0f} is below minimum ₹{MIN_ANNUAL_INCOME:,.0f}",
            value=annual_income,
        )
    if annual_income > MAX_ANNUAL_INCOME:
        return ValidationError(
            field="annual_income",
            message=f"Annual income ₹{annual_income:,.0f} exceeds rural maximum ₹{MAX_ANNUAL_INCOME:,.0f}",
            value=annual_income,
        )
    return None


def validate_loan_amount(amount: float) -> ValidationError | None:
    if amount < MIN_LOAN_AMOUNT:
        return ValidationError(
            field="loan_amount",
            message=f"Loan amount ₹{amount:,.0f} is below minimum ₹{MIN_LOAN_AMOUNT:,.0f}",
            value=amount,
        )
    if amount > MAX_LOAN_AMOUNT:
        return ValidationError(
            field="loan_amount",
            message=f"Loan amount ₹{amount:,.0f} exceeds maximum ₹{MAX_LOAN_AMOUNT:,.0f}",
            value=amount,
        )
    return None


def validate_land_holding(acres: float) -> ValidationError | None:
    if acres < MIN_LAND_HOLDING_ACRES:
        return ValidationError(
            field="land_holding_acres",
            message="Land holding cannot be negative",
            value=acres,
        )
    if acres > MAX_LAND_HOLDING_ACRES:
        return ValidationError(
            field="land_holding_acres",
            message=f"Land holding {acres} acres exceeds maximum {MAX_LAND_HOLDING_ACRES}",
            value=acres,
        )
    return None


def validate_interest_rate(rate: float) -> ValidationError | None:
    if rate < MIN_INTEREST_RATE:
        return ValidationError(
            field="interest_rate",
            message="Interest rate cannot be negative",
            value=rate,
        )
    if rate > MAX_INTEREST_RATE:
        return ValidationError(
            field="interest_rate",
            message=f"Interest rate {rate}% exceeds maximum {MAX_INTEREST_RATE}%",
            value=rate,
        )
    return None


def validate_dependents(count: int) -> ValidationError | None:
    if count < 0:
        return ValidationError(
            field="dependents",
            message="Number of dependents cannot be negative",
            value=count,
        )
    if count > MAX_DEPENDENTS:
        return ValidationError(
            field="dependents",
            message=f"Number of dependents {count} exceeds maximum {MAX_DEPENDENTS}",
            value=count,
        )
    return None
