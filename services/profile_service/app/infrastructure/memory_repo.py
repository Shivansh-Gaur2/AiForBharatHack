"""In-memory repository implementation for the Profile Service.

This adapter fulfils the ProfileRepository port using plain Python dicts.
It is the default storage backend for local development and testing —
no AWS credentials or DynamoDB Local required.
"""

from __future__ import annotations

from services.profile_service.app.domain.models import BorrowerProfile
from services.shared.models import ProfileId


class InMemoryProfileRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        self._profiles: dict[ProfileId, BorrowerProfile] = {}
        # phone → profile_id lookup
        self._phone_index: dict[str, ProfileId] = {}

    # ------------------------------------------------------------------
    # ProfileRepository protocol
    # ------------------------------------------------------------------

    def save(self, profile: BorrowerProfile) -> None:
        self._profiles[profile.profile_id] = profile
        if profile.personal_info.phone:
            self._phone_index[profile.personal_info.phone] = profile.profile_id

    def find_by_id(self, profile_id: ProfileId) -> BorrowerProfile | None:
        return self._profiles.get(profile_id)

    def find_by_phone(self, phone: str) -> BorrowerProfile | None:
        pid = self._phone_index.get(phone)
        if pid is None:
            return None
        return self._profiles.get(pid)

    def find_by_district(self, district: str, state: str) -> list[BorrowerProfile]:
        return [
            p for p in self._profiles.values()
            if (
                p.personal_info.district.lower() == district.lower()
                and p.personal_info.state.lower() == state.lower()
            )
        ]

    def delete(self, profile_id: ProfileId) -> None:
        profile = self._profiles.pop(profile_id, None)
        if profile and profile.personal_info.phone:
            self._phone_index.pop(profile.personal_info.phone, None)

    def list_all(
        self,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[BorrowerProfile], str | None]:
        all_ids = sorted(self._profiles.keys())
        # cursor is the last profile_id seen
        if cursor:
            try:
                start = all_ids.index(cursor) + 1
            except ValueError:
                start = 0
        else:
            start = 0
        page = all_ids[start : start + limit]
        next_cursor = page[-1] if len(page) == limit else None
        return [self._profiles[pid] for pid in page], next_cursor
