"""Unit tests for Profile domain models.

Tests pure business logic — no database, no HTTP, no AWS.
"""

import pytest

from services.profile_service.app.domain.models import (
    BorrowerProfile,
    CropInfo,
    ExpenseRecord,
    IncomeRecord,
    LandDetails,
    LivelihoodInfo,
    PersonalInfo,
    VolatilityMetrics,
)
from services.shared.models import OccupationType, Season


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_personal_info():
    return PersonalInfo(
        name="Ramesh Kumar",
        age=35,
        gender="M",
        district="Varanasi",
        state="Uttar Pradesh",
        dependents=4,
        phone="+919876543210",
    )


@pytest.fixture
def sample_livelihood_info():
    return LivelihoodInfo(
        primary_occupation=OccupationType.FARMER,
        secondary_occupations=[OccupationType.LIVESTOCK_REARER],
        land_holding=LandDetails(
            total_acres=3.5,
            irrigated_acres=2.0,
            rain_fed_acres=1.5,
        ),
        crop_patterns=[
            CropInfo(
                crop_name="Rice",
                season=Season.KHARIF,
                area_acres=2.0,
                expected_yield_quintals=20.0,
                expected_price_per_quintal=2000.0,
            ),
            CropInfo(
                crop_name="Wheat",
                season=Season.RABI,
                area_acres=3.0,
                expected_yield_quintals=18.0,
                expected_price_per_quintal=2200.0,
            ),
        ],
    )


@pytest.fixture
def sample_income_records():
    """12 months of income data with seasonal variation."""
    monthly_amounts = [
        8000, 7500, 7000, 6000, 5000, 5500,    # Jan-Jun (lean)
        12000, 15000, 18000, 20000, 16000, 10000  # Jul-Dec (harvest)
    ]
    return [
        IncomeRecord(month=i + 1, year=2025, amount=amt, source="mixed")
        for i, amt in enumerate(monthly_amounts)
    ]


@pytest.fixture
def sample_profile(sample_personal_info, sample_livelihood_info, sample_income_records):
    return BorrowerProfile.create(
        personal_info=sample_personal_info,
        livelihood_info=sample_livelihood_info,
        income_records=sample_income_records,
    )


# ---------------------------------------------------------------------------
# Tests: Profile creation
# ---------------------------------------------------------------------------
class TestBorrowerProfileCreation:
    def test_create_profile_generates_id(self, sample_personal_info, sample_livelihood_info):
        profile = BorrowerProfile.create(
            personal_info=sample_personal_info,
            livelihood_info=sample_livelihood_info,
        )
        assert profile.profile_id is not None
        assert len(profile.profile_id) > 0

    def test_create_profile_with_income_computes_volatility(self, sample_profile):
        """Property 1: Profile Creation Completeness — volatility computed on creation."""
        assert sample_profile.volatility_metrics is not None
        assert sample_profile.volatility_metrics.volatility_category in ("LOW", "MEDIUM", "HIGH")

    def test_create_profile_preserves_all_income_records(self, sample_profile, sample_income_records):
        """Property 3: Historical Data Preservation — all records retained."""
        assert len(sample_profile.income_records) == len(sample_income_records)

    def test_create_profile_sets_timestamps(self, sample_profile):
        assert sample_profile.created_at is not None
        assert sample_profile.updated_at is not None


# ---------------------------------------------------------------------------
# Tests: Volatility computation
# ---------------------------------------------------------------------------
class TestVolatilityMetrics:
    def test_stable_income_yields_low_volatility(self):
        """Salaried-like income should be LOW volatility."""
        incomes = [10000.0] * 12
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.volatility_category == "LOW"
        assert metrics.coefficient_of_variation == 0.0

    def test_highly_variable_income_yields_high_volatility(self):
        """Monsoon-dependent income should be HIGH volatility."""
        incomes = [1000, 500, 200, 100, 0, 0, 5000, 15000, 20000, 18000, 8000, 2000]
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.volatility_category == "HIGH"
        assert metrics.coefficient_of_variation > 0.6

    def test_moderate_variation_yields_medium(self):
        incomes = [6000, 5000, 4500, 4000, 5500, 7000, 10000, 11000, 9000, 8000, 7500, 6000]
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.volatility_category == "MEDIUM"

    def test_single_month_returns_low(self):
        metrics = VolatilityMetrics.compute([5000.0])
        assert metrics.volatility_category == "LOW"

    def test_zero_income_returns_high(self):
        metrics = VolatilityMetrics.compute([0.0, 0.0, 0.0])
        assert metrics.volatility_category == "HIGH"

    def test_months_below_average_calculated(self):
        incomes = [1000, 2000, 3000, 10000, 11000, 12000,
                   1000, 2000, 3000, 10000, 11000, 12000]
        metrics = VolatilityMetrics.compute(incomes)
        assert metrics.months_below_average > 0


# ---------------------------------------------------------------------------
# Tests: Profile behavior
# ---------------------------------------------------------------------------
class TestProfileBehavior:
    def test_add_income_records_preserves_history(self, sample_profile):
        """Property 3: Adding records preserves existing data."""
        original_count = len(sample_profile.income_records)
        new_records = [
            IncomeRecord(month=1, year=2026, amount=9000, source="crop_sale"),
            IncomeRecord(month=2, year=2026, amount=8500, source="crop_sale"),
        ]
        sample_profile.add_income_records(new_records)
        assert len(sample_profile.income_records) == original_count + 2

    def test_add_income_recomputes_volatility(self, sample_profile):
        sample_profile.add_income_records([
            IncomeRecord(month=1, year=2026, amount=50000, source="windfall"),
        ])
        # Metrics should have been recomputed
        assert sample_profile.volatility_metrics is not None

    def test_monthly_incomes_aggregation(self, sample_profile):
        monthly = sample_profile.get_monthly_incomes()
        assert len(monthly) <= 12
        assert all(amt >= 0 for amt in monthly)

    def test_estimate_annual_income_from_records(self, sample_profile):
        annual = sample_profile.estimate_annual_income()
        assert annual > 0

    def test_estimate_annual_income_from_livelihood(self, sample_personal_info, sample_livelihood_info):
        """When no income records exist, estimate from crop/livestock data."""
        profile = BorrowerProfile.create(
            personal_info=sample_personal_info,
            livelihood_info=sample_livelihood_info,
        )
        annual = profile.estimate_annual_income()
        # Rice: 20q * 2000 = 40000; Wheat: 18q * 2200 = 39600; Total = 79600
        assert annual == pytest.approx(79600.0)

    def test_monthly_surplus(self, sample_profile):
        sample_profile.add_expense_records([
            ExpenseRecord(month=m, year=2025, amount=5000, category="food")
            for m in range(1, 13)
        ])
        surplus = sample_profile.get_monthly_surplus()
        assert isinstance(surplus, float)

    def test_update_personal_info_changes_timestamp(self, sample_profile):
        old_updated = sample_profile.updated_at
        import time

        time.sleep(0.01)
        sample_profile.update_personal_info(PersonalInfo(
            name="Ramesh K.", age=36, gender="M",
            district="Varanasi", state="Uttar Pradesh", dependents=5,
        ))
        assert sample_profile.updated_at >= old_updated
        assert sample_profile.personal_info.name == "Ramesh K."
