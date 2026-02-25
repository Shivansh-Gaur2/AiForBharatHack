"""Profile domain validators — rural-context business rules.

These validators enforce domain-specific constraints that go beyond
simple type/range checks (which live in shared/validation).
"""

from __future__ import annotations

from services.shared.validation import (
    ValidationError,
    ValidationResult,
    validate_dependents,
    validate_income,
    validate_land_holding,
)

from .models import (
    IncomeRecord,
    LivelihoodInfo,
    PersonalInfo,
)


def validate_personal_info(info: PersonalInfo) -> ValidationResult:
    """Validate personal information against rural context rules."""
    errors: list[ValidationError] = []

    if not info.name or len(info.name.strip()) < 2:
        errors.append(ValidationError("name", "Name must be at least 2 characters"))

    if info.age < 18:
        errors.append(ValidationError("age", "Borrower must be at least 18 years old", info.age))

    if info.age > 100:
        errors.append(ValidationError("age", "Age exceeds reasonable maximum of 100", info.age))

    if info.gender not in ("M", "F", "O"):
        errors.append(ValidationError("gender", "Gender must be M, F, or O", info.gender))

    if not info.district:
        errors.append(ValidationError("district", "District is required"))

    if not info.state:
        errors.append(ValidationError("state", "State is required"))

    dep_error = validate_dependents(info.dependents)
    if dep_error:
        errors.append(dep_error)

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_livelihood_info(info: LivelihoodInfo) -> ValidationResult:
    """Validate livelihood information."""
    errors: list[ValidationError] = []

    # Land holding checks
    if info.land_holding:
        land_error = validate_land_holding(info.land_holding.total_acres)
        if land_error:
            errors.append(land_error)

        if info.land_holding.irrigated_acres + info.land_holding.rain_fed_acres > info.land_holding.total_acres * 1.01:
            errors.append(ValidationError(
                "land_holding",
                "Irrigated + rain-fed acres cannot exceed total acres",
            ))

    # Crop pattern checks
    for i, crop in enumerate(info.crop_patterns):
        if crop.area_acres <= 0:
            errors.append(ValidationError(f"crop_patterns[{i}].area_acres", "Crop area must be positive"))
        if crop.expected_yield_quintals < 0:
            errors.append(ValidationError(f"crop_patterns[{i}].expected_yield_quintals", "Yield cannot be negative"))
        if crop.expected_price_per_quintal < 0:
            errors.append(ValidationError(f"crop_patterns[{i}].expected_price_per_quintal", "Price cannot be negative"))

    # Livestock checks
    for i, ls in enumerate(info.livestock):
        if ls.count <= 0:
            errors.append(ValidationError(f"livestock[{i}].count", "Livestock count must be positive"))

    # Migration checks
    for i, mig in enumerate(info.migration_patterns):
        if mig.monthly_income < 0:
            errors.append(ValidationError(f"migration_patterns[{i}].monthly_income", "Migration income cannot be negative"))
        invalid_months = [m for m in mig.months if m < 1 or m > 12]
        if invalid_months:
            errors.append(ValidationError(f"migration_patterns[{i}].months", f"Invalid months: {invalid_months}"))

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_income_records(records: list[IncomeRecord]) -> ValidationResult:
    """Validate a batch of income records."""
    errors: list[ValidationError] = []

    for i, rec in enumerate(records):
        if rec.amount < 0:
            errors.append(ValidationError(f"income_records[{i}].amount", "Income amount cannot be negative", rec.amount))
        if rec.month < 1 or rec.month > 12:
            errors.append(ValidationError(f"income_records[{i}].month", f"Invalid month: {rec.month}", rec.month))
        if rec.year < 2000 or rec.year > 2100:
            errors.append(ValidationError(f"income_records[{i}].year", f"Year out of range: {rec.year}", rec.year))

    # Validate total annual income
    if records:
        annual = sum(r.amount for r in records)
        income_error = validate_income(annual)
        if income_error:
            errors.append(income_error)

    return ValidationResult.ok() if not errors else ValidationResult.fail(errors)


def validate_profile_for_creation(
    personal_info: PersonalInfo,
    livelihood_info: LivelihoodInfo,
    income_records: list[IncomeRecord],
) -> ValidationResult:
    """Full validation for profile creation — combines all validators."""
    result = validate_personal_info(personal_info)
    result = result.merge(validate_livelihood_info(livelihood_info))
    if income_records:
        result = result.merge(validate_income_records(income_records))
    return result
