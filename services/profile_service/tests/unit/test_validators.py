"""Unit tests for domain validators."""


from services.profile_service.app.domain.models import (
    IncomeRecord,
    LandDetails,
    LivelihoodInfo,
    PersonalInfo,
)
from services.profile_service.app.domain.validators import (
    validate_income_records,
    validate_livelihood_info,
    validate_personal_info,
    validate_profile_for_creation,
)
from services.shared.models import OccupationType


class TestPersonalInfoValidation:
    def test_valid_info_passes(self):
        info = PersonalInfo(
            name="Test User", age=25, gender="M",
            district="Test", state="Test", dependents=2,
        )
        result = validate_personal_info(info)
        assert result.is_valid

    def test_underage_fails(self):
        info = PersonalInfo(
            name="Young Person", age=16, gender="M",
            district="Test", state="Test", dependents=0,
        )
        result = validate_personal_info(info)
        assert not result.is_valid
        assert any("18" in e.message for e in result.errors)

    def test_empty_name_fails(self):
        info = PersonalInfo(
            name="", age=25, gender="M",
            district="Test", state="Test", dependents=0,
        )
        result = validate_personal_info(info)
        assert not result.is_valid

    def test_invalid_gender_fails(self):
        info = PersonalInfo(
            name="Test", age=25, gender="X",
            district="Test", state="Test", dependents=0,
        )
        result = validate_personal_info(info)
        assert not result.is_valid

    def test_negative_dependents_fails(self):
        info = PersonalInfo(
            name="Test", age=25, gender="M",
            district="Test", state="Test", dependents=-1,
        )
        result = validate_personal_info(info)
        assert not result.is_valid


class TestLivelihoodValidation:
    def test_valid_livelihood_passes(self):
        info = LivelihoodInfo(primary_occupation=OccupationType.FARMER)
        result = validate_livelihood_info(info)
        assert result.is_valid

    def test_land_exceeding_max_fails(self):
        info = LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            land_holding=LandDetails(
                total_acres=150, irrigated_acres=100, rain_fed_acres=50,
            ),
        )
        result = validate_livelihood_info(info)
        assert not result.is_valid

    def test_irrigated_plus_rainfed_exceeds_total_fails(self):
        info = LivelihoodInfo(
            primary_occupation=OccupationType.FARMER,
            land_holding=LandDetails(
                total_acres=5, irrigated_acres=3, rain_fed_acres=3,
            ),
        )
        result = validate_livelihood_info(info)
        assert not result.is_valid


class TestIncomeRecordValidation:
    def test_valid_records_pass(self):
        records = [
            IncomeRecord(month=m, year=2025, amount=5000, source="farm")
            for m in range(1, 13)
        ]
        result = validate_income_records(records)
        assert result.is_valid

    def test_negative_amount_fails(self):
        records = [IncomeRecord(month=1, year=2025, amount=-100, source="farm")]
        result = validate_income_records(records)
        assert not result.is_valid

    def test_invalid_month_fails(self):
        records = [IncomeRecord(month=13, year=2025, amount=5000, source="farm")]
        result = validate_income_records(records)
        assert not result.is_valid


class TestProfileCreationValidation:
    def test_full_validation_passes(self):
        result = validate_profile_for_creation(
            PersonalInfo(
                name="Valid Person", age=30, gender="F",
                district="Test", state="Test", dependents=2,
            ),
            LivelihoodInfo(primary_occupation=OccupationType.FARMER),
            [IncomeRecord(month=m, year=2025, amount=8000, source="farm") for m in range(1, 13)],
        )
        assert result.is_valid

    def test_multiple_errors_collected(self):
        result = validate_profile_for_creation(
            PersonalInfo(
                name="", age=10, gender="X",
                district="", state="", dependents=-5,
            ),
            LivelihoodInfo(
                primary_occupation=OccupationType.FARMER,
                land_holding=LandDetails(total_acres=200, irrigated_acres=0, rain_fed_acres=0),
            ),
            [IncomeRecord(month=1, year=2025, amount=-100, source="bad")],
        )
        assert not result.is_valid
        assert len(result.errors) >= 4  # multiple errors collected
