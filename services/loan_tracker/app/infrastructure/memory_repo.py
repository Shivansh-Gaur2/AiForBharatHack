"""In-memory repository implementation for the Loan Tracker service.

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.loan_tracker.app.domain.models import Loan
from services.shared.models import LoanStatus, ProfileId, TrackingId


class InMemoryLoanRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        self._loans: dict[TrackingId, Loan] = {}

    # ------------------------------------------------------------------
    # LoanRepository protocol (all async to match the protocol)
    # ------------------------------------------------------------------

    async def save(self, loan: Loan) -> None:
        self._loans[loan.tracking_id] = loan

    async def find_by_id(self, tracking_id: TrackingId) -> Loan | None:
        return self._loans.get(tracking_id)

    async def find_by_profile(
        self,
        profile_id: ProfileId,
        active_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]:
        loans = [
            l for l in self._loans.values()
            if l.profile_id == profile_id
        ]
        if active_only:
            loans = [
                l for l in loans
                if l.status not in (LoanStatus.CLOSED, LoanStatus.DEFAULTED)
            ]
        loans.sort(key=lambda l: l.created_at)

        if cursor:
            ids = [l.tracking_id for l in loans]
            try:
                start = ids.index(cursor) + 1
            except ValueError:
                start = 0
        else:
            start = 0

        page = loans[start : start + limit]
        next_cursor = page[-1].tracking_id if len(page) == limit else None
        return page, next_cursor

    async def delete(self, tracking_id: TrackingId) -> bool:
        if tracking_id in self._loans:
            del self._loans[tracking_id]
            return True
        return False

    async def delete_by_profile(self, profile_id: ProfileId) -> int:
        ids_to_delete = [
            tid for tid, loan in self._loans.items()
            if loan.profile_id == profile_id
        ]
        for tid in ids_to_delete:
            del self._loans[tid]
        return len(ids_to_delete)

    async def list_all(
        self,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]:
        all_loans = sorted(self._loans.values(), key=lambda l: l.created_at)

        if cursor:
            ids = [l.tracking_id for l in all_loans]
            try:
                start = ids.index(cursor) + 1
            except ValueError:
                start = 0
        else:
            start = 0

        page = all_loans[start : start + limit]
        next_cursor = page[-1].tracking_id if len(page) == limit else None
        return page, next_cursor
