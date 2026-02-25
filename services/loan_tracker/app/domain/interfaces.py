"""Domain interfaces (ports) for the Loan Tracker service.

These are abstract contracts that infrastructure adapters must implement.
The domain layer depends ONLY on these protocols, never on DynamoDB/SQS/etc.
"""

from __future__ import annotations

from typing import Protocol

from services.shared.models import ProfileId, TrackingId

from .models import Loan


class LoanRepository(Protocol):
    """Port: persistence for Loan aggregates."""

    async def save(self, loan: Loan) -> None: ...

    async def find_by_id(self, tracking_id: TrackingId) -> Loan | None: ...

    async def find_by_profile(
        self,
        profile_id: ProfileId,
        active_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]: ...

    async def delete(self, tracking_id: TrackingId) -> bool: ...

    async def list_all(
        self,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]: ...
