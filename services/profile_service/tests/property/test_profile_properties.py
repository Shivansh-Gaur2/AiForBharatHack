"""Property-based tests for Profile domain logic.

Uses Hypothesis to verify universal properties across all valid inputs.
Each test references its design document property.

Minimum 100 iterations per property test (configured via settings).
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services.profile_service.app.domain.models import (
    BorrowerProfile,
    IncomeRecord,
    LivelihoodInfo,
    PersonalInfo,
    VolatilityMetrics,
)
from services.profile_service.app.domain.validators import (
    validate_personal_info,
    validate_profile_for_creation,
)
from services.shared.models import OccupationType

# ---------------------------------------------------------------------------
# Hypothesis strategies — generate valid domain objects
# ---------------------------------------------------------------------------
valid_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "Zs")),
    min_size=2, max_size=100,
).filter(lambda s: len(s.strip()) >= 2)

valid_personal_info = st.builds(
    PersonalInfo,
    name=valid_names,
    age=st.integers(min_value=18, max_value=100),
    gender=st.sampled_from(["M", "F", "O"]),
    district=st.text(min_size=1, max_size=50).filter(lambda s: len(s.strip()) >= 1),
    state=st.text(min_size=1, max_size=50).filter(lambda s: len(s.strip()) >= 1),
    dependents=st.integers(min_value=0, max_value=20),
    phone=st.none(),
)

valid_livelihood_info = st.builds(
    LivelihoodInfo,
    primary_occupation=st.sampled_from(list(OccupationType)),
)

valid_monthly_incomes = st.lists(
    st.floats(min_value=100, max_value=200000, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=24,
)

valid_income_records = st.lists(
    st.builds(
        IncomeRecord,
        month=st.integers(min_value=1, max_value=12),
        year=st.integers(min_value=2020, max_value=2026),
        amount=st.floats(min_value=0, max_value=200000, allow_nan=False, allow_infinity=False),
        source=st.sampled_from(["crop_sale", "wage", "livestock", "migration", "other"]),
        is_verified=st.booleans(),
    ),
    min_size=1,
    max_size=24,
)


# ---------------------------------------------------------------------------
# Property 1: Profile Creation Completeness
# ---------------------------------------------------------------------------
class TestProperty1ProfileCreationCompleteness:
    """Feature: rural-credit-ai-advisor, Property 1: Profile Creation Completeness

    For any valid borrower input data, creating a Credit_Profile should result
    in a complete profile with all required fields populated, seasonal patterns
    incorporated, and volatility metrics calculated.
    """

    @given(personal=valid_personal_info, livelihood=valid_livelihood_info)
    @settings(max_examples=100)
    def test_profile_always_has_id_and_timestamps(self, personal, livelihood):
        profile = BorrowerProfile.create(
            personal_info=personal,
            livelihood_info=livelihood,
        )
        assert profile.profile_id is not None
        assert len(profile.profile_id) > 0
        assert profile.created_at is not None
        assert profile.updated_at is not None

    @given(
        personal=valid_personal_info,
        livelihood=valid_livelihood_info,
        records=valid_income_records,
    )
    @settings(max_examples=100)
    def test_profile_with_income_always_has_volatility(self, personal, livelihood, records):
        profile = BorrowerProfile.create(
            personal_info=personal,
            livelihood_info=livelihood,
            income_records=records,
        )
        # If income records were added, volatility must be computed
        if profile.get_monthly_incomes():
            assert profile.volatility_metrics is not None
            assert profile.volatility_metrics.volatility_category in ("LOW", "MEDIUM", "HIGH")


# ---------------------------------------------------------------------------
# Property 2: Data Validation Consistency
# ---------------------------------------------------------------------------
class TestProperty2DataValidationConsistency:
    """Feature: rural-credit-ai-advisor, Property 2: Data Validation Consistency

    For any input data, the AI_Advisor should consistently validate against
    rural context ranges, rejecting invalid data and accepting valid data
    according to the same criteria.
    """

    @given(personal=valid_personal_info)
    @settings(max_examples=100)
    def test_valid_personal_info_always_passes(self, personal):
        result = validate_personal_info(personal)
        assert result.is_valid

    @given(age=st.integers(min_value=-100, max_value=17))
    @settings(max_examples=100)
    def test_underage_always_rejected(self, age):
        info = PersonalInfo(
            name="Test", age=age, gender="M",
            district="Test", state="Test", dependents=0,
        )
        result = validate_personal_info(info)
        assert not result.is_valid

    @given(
        personal=valid_personal_info,
        livelihood=valid_livelihood_info,
    )
    @settings(max_examples=100)
    def test_validation_is_idempotent(self, personal, livelihood):
        """Running validation twice on same input gives same result."""
        result1 = validate_profile_for_creation(personal, livelihood, [])
        result2 = validate_profile_for_creation(personal, livelihood, [])
        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)


# ---------------------------------------------------------------------------
# Property 3: Historical Data Preservation
# ---------------------------------------------------------------------------
class TestProperty3HistoricalDataPreservation:
    """Feature: rural-credit-ai-advisor, Property 3: Historical Data Preservation

    For any profile update operation, all historical patterns and trend data
    should remain intact and accessible for analysis.
    """

    @given(
        personal=valid_personal_info,
        livelihood=valid_livelihood_info,
        batch1=valid_income_records,
        batch2=valid_income_records,
    )
    @settings(max_examples=100)
    def test_adding_records_never_removes_existing(self, personal, livelihood, batch1, batch2):
        profile = BorrowerProfile.create(
            personal_info=personal,
            livelihood_info=livelihood,
            income_records=batch1,
        )
        count_after_first = len(profile.income_records)

        profile.add_income_records(batch2)
        count_after_second = len(profile.income_records)

        assert count_after_second == count_after_first + len(batch2)

    @given(
        personal=valid_personal_info,
        livelihood=valid_livelihood_info,
        records=valid_income_records,
    )
    @settings(max_examples=100)
    def test_update_personal_info_preserves_income_records(self, personal, livelihood, records):
        profile = BorrowerProfile.create(
            personal_info=personal,
            livelihood_info=livelihood,
            income_records=records,
        )
        original_records = list(profile.income_records)

        new_personal = PersonalInfo(
            name="Updated Name", age=30, gender="F",
            district="New District", state="New State", dependents=1,
        )
        profile.update_personal_info(new_personal)

        assert profile.income_records == original_records


# ---------------------------------------------------------------------------
# Volatility computation properties
# ---------------------------------------------------------------------------
class TestVolatilityComputationProperties:
    """Verify mathematical properties of volatility calculation."""

    @given(incomes=valid_monthly_incomes)
    @settings(max_examples=200)
    def test_cv_is_non_negative(self, incomes):
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.coefficient_of_variation >= 0

    @given(amount=st.floats(min_value=100, max_value=200000, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_constant_income_has_zero_cv(self, amount):
        """If all months have the same income, CV should be 0."""
        incomes = [amount] * 12
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.coefficient_of_variation == pytest.approx(0.0, abs=1e-10)
        assert metrics.volatility_category == "LOW"

    @given(incomes=valid_monthly_incomes)
    @settings(max_examples=100)
    def test_months_below_average_bounded(self, incomes):
        metrics = VolatilityMetrics.compute(incomes)
        assert 0 <= metrics.months_below_average <= len(incomes)

    @given(incomes=valid_monthly_incomes)
    @settings(max_examples=100)
    def test_category_is_always_valid(self, incomes):
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.volatility_category in ("LOW", "MEDIUM", "HIGH")
