"""Shared pytest fixtures for Profile Service tests."""

import pytest

from services.profile_service.app.domain.models import (
    BorrowerProfile,
    IncomeRecord,
    LivelihoodInfo,
    PersonalInfo,
)
from services.shared.events import InMemoryEventPublisher
from services.shared.models import OccupationType

# ── In-memory repository test double ──────────────────────────────────────

class InMemoryProfileRepository:
    """Simple dict-backed repository for unit tests."""

    def __init__(self):
        self._store: dict[str, BorrowerProfile] = {}

    async def save(self, profile: BorrowerProfile) -> None:
        self._store[profile.profile_id] = profile

    async def find_by_id(self, profile_id: str) -> BorrowerProfile | None:
        return self._store.get(profile_id)

    async def find_by_phone(self, phone: str) -> BorrowerProfile | None:
        for p in self._store.values():
            if p.personal_info.phone == phone:
                return p
        return None

    async def find_by_district(
        self, state: str, district: str, limit: int = 20, cursor: str | None = None,
    ) -> tuple[list[BorrowerProfile], str | None]:
        matches = [
            p for p in self._store.values()
            if p.personal_info.state == state and p.personal_info.district == district
        ]
        return matches[:limit], None

    async def delete(self, profile_id: str) -> bool:
        return self._store.pop(profile_id, None) is not None

    async def list_all(
        self, limit: int = 20, cursor: str | None = None,
    ) -> tuple[list[BorrowerProfile], str | None]:
        profiles = list(self._store.values())
        return profiles[:limit], None


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def repo():
    return InMemoryProfileRepository()


@pytest.fixture
def event_publisher():
    return InMemoryEventPublisher()


@pytest.fixture
def sample_personal_info():
    return PersonalInfo(
        name="Test Farmer",
        age=35,
        gender="M",
        district="Varanasi",
        state="Uttar Pradesh",
        dependents=3,
        phone="+919876543210",
    )


@pytest.fixture
def sample_livelihood_info():
    return LivelihoodInfo(primary_occupation=OccupationType.FARMER)


@pytest.fixture
def sample_income_records():
    return [
        IncomeRecord(month=m, year=2024, amount=8000 + m * 500, source="crop_sale")
        for m in range(1, 13)
    ]
