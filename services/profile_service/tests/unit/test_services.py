"""Unit tests for Profile domain service.

Tests business logic orchestration with mock repository and event publisher.
No real database or AWS services needed.
"""


import pytest

from services.profile_service.app.domain.models import (
    BorrowerProfile,
    IncomeRecord,
    LivelihoodInfo,
    PersonalInfo,
)
from services.profile_service.app.domain.services import ProfileService
from services.shared.events import InMemoryEventPublisher
from services.shared.models import OccupationType


# ---------------------------------------------------------------------------
# In-memory repository (test double)
# ---------------------------------------------------------------------------
class InMemoryProfileRepository:
    """Simple dict-backed repository for unit testing."""

    def __init__(self):
        self._store: dict[str, BorrowerProfile] = {}

    def save(self, profile: BorrowerProfile) -> None:
        self._store[profile.profile_id] = profile

    def find_by_id(self, profile_id: str):
        return self._store.get(profile_id)

    def find_by_phone(self, phone: str):
        for p in self._store.values():
            if p.personal_info.phone == phone:
                return p
        return None

    def find_by_district(self, district: str, state: str):
        return [
            p for p in self._store.values()
            if p.personal_info.district == district and p.personal_info.state == state
        ]

    def delete(self, profile_id: str) -> None:
        self._store.pop(profile_id, None)

    def list_all(self, limit=50, cursor=None):
        profiles = list(self._store.values())[:limit]
        return profiles, None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def repo():
    return InMemoryProfileRepository()


@pytest.fixture
def events():
    return InMemoryEventPublisher()


@pytest.fixture
def service(repo, events):
    return ProfileService(repository=repo, event_publisher=events)


@pytest.fixture
def valid_personal_info():
    return PersonalInfo(
        name="Sunita Devi",
        age=28,
        gender="F",
        district="Patna",
        state="Bihar",
        dependents=3,
        phone="+919988776655",
    )


@pytest.fixture
def valid_livelihood_info():
    return LivelihoodInfo(
        primary_occupation=OccupationType.SHG_MEMBER,
    )


@pytest.fixture
def valid_income_records():
    return [
        IncomeRecord(month=m, year=2025, amount=5000 + m * 500, source="shg_loan_interest")
        for m in range(1, 13)
    ]


# ---------------------------------------------------------------------------
# Tests: Profile creation
# ---------------------------------------------------------------------------
class TestCreateProfile:
    def test_creates_profile_successfully(self, service, valid_personal_info, valid_livelihood_info):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        assert profile.profile_id is not None
        assert profile.personal_info.name == "Sunita Devi"

    def test_creates_profile_with_income_records(
        self, service, valid_personal_info, valid_livelihood_info, valid_income_records
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
            income_records=valid_income_records,
        )
        assert len(profile.income_records) == 12
        assert profile.volatility_metrics is not None

    def test_publishes_profile_created_event(
        self, service, events, valid_personal_info, valid_livelihood_info
    ):
        service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        assert len(events.events) == 1
        assert events.events[0].event_type == "profile.created"

    def test_persists_profile_in_repository(
        self, service, repo, valid_personal_info, valid_livelihood_info
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        found = repo.find_by_id(profile.profile_id)
        assert found is not None
        assert found.profile_id == profile.profile_id

    def test_rejects_invalid_personal_info(self, service, valid_livelihood_info):
        invalid_info = PersonalInfo(
            name="",  # invalid: too short
            age=15,   # invalid: under 18
            gender="X",  # invalid
            district="",
            state="",
            dependents=-1,
        )
        with pytest.raises(ValueError, match="validation failed"):
            service.create_profile(
                personal_info=invalid_info,
                livelihood_info=valid_livelihood_info,
            )


# ---------------------------------------------------------------------------
# Tests: Profile retrieval
# ---------------------------------------------------------------------------
class TestGetProfile:
    def test_retrieves_existing_profile(self, service, valid_personal_info, valid_livelihood_info):
        created = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        found = service.get_profile(created.profile_id)
        assert found.profile_id == created.profile_id

    def test_raises_on_nonexistent_profile(self, service):
        with pytest.raises(KeyError, match="Profile not found"):
            service.get_profile("nonexistent-id")


# ---------------------------------------------------------------------------
# Tests: Income records
# ---------------------------------------------------------------------------
class TestAddIncomeRecords:
    def test_adds_records_and_recomputes_volatility(
        self, service, valid_personal_info, valid_livelihood_info, valid_income_records
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        updated = service.add_income_records(profile.profile_id, valid_income_records)
        assert len(updated.income_records) == 12
        assert updated.volatility_metrics is not None

    def test_preserves_existing_records(
        self, service, valid_personal_info, valid_livelihood_info, valid_income_records
    ):
        """Property 3: Historical Data Preservation."""
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
            income_records=valid_income_records,
        )
        new_records = [
            IncomeRecord(month=1, year=2026, amount=9000, source="crop"),
        ]
        updated = service.add_income_records(profile.profile_id, new_records)
        assert len(updated.income_records) == 13  # 12 original + 1 new

    def test_publishes_income_updated_event(
        self, service, events, valid_personal_info, valid_livelihood_info, valid_income_records
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        events.events.clear()
        service.add_income_records(profile.profile_id, valid_income_records)
        assert any(e.event_type == "profile.income_updated" for e in events.events)

    def test_rejects_negative_income(
        self, service, valid_personal_info, valid_livelihood_info
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        bad_records = [IncomeRecord(month=1, year=2025, amount=-5000, source="error")]
        with pytest.raises(ValueError):
            service.add_income_records(profile.profile_id, bad_records)


# ---------------------------------------------------------------------------
# Tests: Update operations
# ---------------------------------------------------------------------------
class TestUpdateProfile:
    def test_update_personal_info(
        self, service, valid_personal_info, valid_livelihood_info
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        new_info = PersonalInfo(
            name="Sunita Kumari",
            age=29,
            gender="F",
            district="Patna",
            state="Bihar",
            dependents=4,
        )
        updated = service.update_personal_info(profile.profile_id, new_info)
        assert updated.personal_info.name == "Sunita Kumari"
        assert updated.personal_info.dependents == 4

    def test_update_publishes_event(
        self, service, events, valid_personal_info, valid_livelihood_info
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        events.events.clear()
        service.update_personal_info(profile.profile_id, valid_personal_info)
        assert any(e.event_type == "profile.updated" for e in events.events)


# ---------------------------------------------------------------------------
# Tests: Volatility queries
# ---------------------------------------------------------------------------
class TestVolatilityQueries:
    def test_get_volatility_metrics(
        self, service, valid_personal_info, valid_livelihood_info, valid_income_records
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
            income_records=valid_income_records,
        )
        metrics = service.get_volatility_metrics(profile.profile_id)
        assert metrics.volatility_category in ("LOW", "MEDIUM", "HIGH")

    def test_volatility_without_records_raises(
        self, service, valid_personal_info, valid_livelihood_info
    ):
        profile = service.create_profile(
            personal_info=valid_personal_info,
            livelihood_info=valid_livelihood_info,
        )
        with pytest.raises(ValueError, match="Add income records"):
            service.get_volatility_metrics(profile.profile_id)


# ---------------------------------------------------------------------------
# Tests: Pagination
# ---------------------------------------------------------------------------
class TestListProfiles:
    def test_list_returns_profiles(
        self, service, valid_personal_info, valid_livelihood_info
    ):
        for _ in range(3):
            service.create_profile(
                personal_info=valid_personal_info,
                livelihood_info=valid_livelihood_info,
            )
        profiles, _cursor = service.list_profiles(limit=10)
        assert len(profiles) == 3
