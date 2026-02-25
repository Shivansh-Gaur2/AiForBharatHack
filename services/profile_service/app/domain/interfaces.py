"""Domain interfaces (Ports) — abstract contracts for infrastructure to implement.

These are Python Protocols (structural subtyping). The domain layer depends
on these interfaces, never on concrete implementations like DynamoDB or SQS.
"""

from __future__ import annotations

from typing import Protocol

from services.profile_service.app.domain.models import BorrowerProfile
from services.shared.models import ProfileId


class ProfileRepository(Protocol):
    """Port for persisting and retrieving borrower profiles."""

    def save(self, profile: BorrowerProfile) -> None:
        """Persist a borrower profile (create or update)."""
        ...

    def find_by_id(self, profile_id: ProfileId) -> BorrowerProfile | None:
        """Retrieve a profile by its ID. Returns None if not found."""
        ...

    def find_by_phone(self, phone: str) -> BorrowerProfile | None:
        """Retrieve a profile by phone number."""
        ...

    def find_by_district(self, district: str, state: str) -> list[BorrowerProfile]:
        """Retrieve profiles by district and state."""
        ...

    def delete(self, profile_id: ProfileId) -> None:
        """Delete a profile by its ID."""
        ...

    def list_all(self, limit: int = 50, cursor: str | None = None) -> tuple[list[BorrowerProfile], str | None]:
        """List profiles with cursor-based pagination.

        Returns (profiles, next_cursor). next_cursor is None if no more pages.
        """
        ...
