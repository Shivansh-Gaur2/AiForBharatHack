"""Loan Tracker domain service — orchestrates loan tracking use cases.

All business logic lives here. Infrastructure is injected via constructor.
Publishes domain events when important state changes occur (Property 5).
"""

from __future__ import annotations

from datetime import datetime

from services.shared.events import AsyncEventPublisher, DomainEvent
from services.shared.models import LoanSourceType, LoanStatus, ProfileId, TrackingId

from .interfaces import LoanRepository
from .models import DebtExposure, Loan, LoanTerms, RepaymentRecord
from .validators import validate_loan_creation, validate_repayment


class LoanTrackerService:
    """Application service for multi-loan tracking (Req 2.1–2.5)."""

    def __init__(
        self,
        repo: LoanRepository,
        events: AsyncEventPublisher,
    ) -> None:
        self._repo = repo
        self._events = events

    # -- Commands ----------------------------------------------------------

    async def track_loan(
        self,
        profile_id: ProfileId,
        lender_name: str,
        source_type: LoanSourceType,
        terms: LoanTerms,
        disbursement_date: datetime,
        maturity_date: datetime | None = None,
        purpose: str = "",
        notes: str = "",
    ) -> Loan:
        """Register a new loan for tracking (Req 2.1)."""
        result = validate_loan_creation(lender_name, terms, disbursement_date)
        if not result.is_valid:
            raise ValueError(
                "Invalid loan data: "
                + "; ".join(e.message for e in result.errors)
            )

        loan = Loan.create(
            profile_id=profile_id,
            lender_name=lender_name,
            source_type=source_type,
            terms=terms,
            disbursement_date=disbursement_date,
            maturity_date=maturity_date,
            purpose=purpose,
            notes=notes,
        )

        await self._repo.save(loan)
        await self._events.publish(DomainEvent(
            event_type="loan.tracked",
            aggregate_id=loan.tracking_id,
            payload={
                "profile_id": profile_id,
                "source_type": source_type.value,
                "principal": terms.principal,
                "lender": lender_name,
            },
        ))

        return loan

    async def record_repayment(
        self,
        tracking_id: TrackingId,
        repayment: RepaymentRecord,
    ) -> Loan:
        """Record a repayment against a tracked loan (Req 2.5)."""
        loan = await self._repo.find_by_id(tracking_id)
        if loan is None:
            raise KeyError(f"Loan {tracking_id} not found")

        if loan.status == LoanStatus.CLOSED:
            raise ValueError("Cannot record repayment on a closed loan")

        result = validate_repayment(repayment, loan)
        if not result.is_valid:
            raise ValueError(
                "Invalid repayment: "
                + "; ".join(e.message for e in result.errors)
            )

        was_active = loan.status == LoanStatus.ACTIVE
        loan.record_repayment(repayment)
        await self._repo.save(loan)

        event_type = (
            "loan.closed" if was_active and loan.status == LoanStatus.CLOSED
            else "loan.repayment_recorded"
        )
        await self._events.publish(DomainEvent(
            event_type=event_type,
            aggregate_id=loan.tracking_id,
            payload={
                "profile_id": loan.profile_id,
                "amount": repayment.amount,
                "outstanding": loan.outstanding_balance,
                "status": loan.status.value,
            },
        ))

        return loan

    async def update_loan_status(
        self,
        tracking_id: TrackingId,
        new_status: LoanStatus,
    ) -> Loan:
        """Update the status of a tracked loan (Req 2.5 — real-time updates)."""
        loan = await self._repo.find_by_id(tracking_id)
        if loan is None:
            raise KeyError(f"Loan {tracking_id} not found")

        old_status = loan.status
        loan.update_status(new_status)
        await self._repo.save(loan)

        await self._events.publish(DomainEvent(
            event_type="loan.status_changed",
            aggregate_id=loan.tracking_id,
            payload={
                "profile_id": loan.profile_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "outstanding": loan.outstanding_balance,
            },
        ))

        return loan

    # -- Queries -----------------------------------------------------------

    async def get_loan(self, tracking_id: TrackingId) -> Loan | None:
        return await self._repo.find_by_id(tracking_id)

    async def get_borrower_loans(
        self,
        profile_id: ProfileId,
        active_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Loan], str | None]:
        return await self._repo.find_by_profile(
            profile_id, active_only=active_only, limit=limit, cursor=cursor,
        )

    async def get_total_exposure(
        self,
        profile_id: ProfileId,
        annual_income: float,
    ) -> DebtExposure:
        """Calculate total debt exposure (Property 4 — aggregation accuracy).

        The invariant: total_outstanding == sum(source.total_outstanding for each source)
        """
        loans, _ = await self._repo.find_by_profile(profile_id, limit=500)
        return DebtExposure.compute(loans, profile_id, annual_income)

    async def get_debt_to_income_ratio(
        self,
        profile_id: ProfileId,
        annual_income: float,
    ) -> float:
        """Convenience: returns just the DTI ratio (Req 2.4)."""
        exposure = await self.get_total_exposure(profile_id, annual_income)
        return exposure.debt_to_income_ratio

    async def delete_profile_data(self, profile_id: ProfileId) -> int:
        """Delete all loan records for a profile (cascade on profile deletion).

        Returns the number of loans deleted.
        """
        return await self._repo.delete_by_profile(profile_id)
