"""Unit tests for LoanTrackerService."""

from datetime import UTC, datetime

import pytest

from services.loan_tracker.app.domain.models import Loan, LoanTerms, RepaymentRecord
from services.loan_tracker.app.domain.services import LoanTrackerService
from services.shared.events import AsyncInMemoryEventPublisher
from services.shared.models import LoanSourceType, LoanStatus


# ---------------------------------------------------------------------------
# In-memory repository test double
# ---------------------------------------------------------------------------
class InMemoryLoanRepository:
    def __init__(self):
        self._store: dict[str, Loan] = {}

    async def save(self, loan: Loan) -> None:
        self._store[loan.tracking_id] = loan

    async def find_by_id(self, tracking_id: str):
        return self._store.get(tracking_id)

    async def find_by_profile(self, profile_id, active_only=False, limit=50, cursor=None):
        loans = [l for l in self._store.values() if l.profile_id == profile_id]
        if active_only:
            loans = [l for l in loans if l.status == LoanStatus.ACTIVE]
        return loans[:limit], None

    async def delete(self, tracking_id):
        return self._store.pop(tracking_id, None) is not None

    async def list_all(self, limit=20, cursor=None):
        return list(self._store.values())[:limit], None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def repo():
    return InMemoryLoanRepository()


@pytest.fixture
def events():
    return AsyncInMemoryEventPublisher()


@pytest.fixture
def service(repo, events):
    return LoanTrackerService(repo=repo, events=events)


def _now():
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestTrackLoan:
    @pytest.mark.asyncio
    async def test_track_loan_creates_and_persists(self, service, repo, events):
        loan = await service.track_loan(
            profile_id="p1",
            lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=50000, interest_rate_annual=10, tenure_months=12, emi_amount=4500),
            disbursement_date=_now(),
        )
        assert loan.status == LoanStatus.ACTIVE
        assert loan.outstanding_balance == 50000

        # Persisted
        stored = await repo.find_by_id(loan.tracking_id)
        assert stored is not None

        # Event published
        assert len(events.events) == 1
        assert events.events[0].event_type == "loan.tracked"

    @pytest.mark.asyncio
    async def test_track_loan_rejects_invalid_data(self, service):
        with pytest.raises(ValueError, match="Lender name"):
            await service.track_loan(
                profile_id="p1",
                lender_name="",
                source_type=LoanSourceType.FORMAL,
                terms=LoanTerms(principal=50000, interest_rate_annual=10, tenure_months=12, emi_amount=4500),
                disbursement_date=_now(),
            )


class TestRecordRepayment:
    @pytest.mark.asyncio
    async def test_repayment_reduces_balance(self, service):
        loan = await service.track_loan(
            profile_id="p1", lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=50000, interest_rate_annual=10, tenure_months=12, emi_amount=4500),
            disbursement_date=_now(),
        )

        updated = await service.record_repayment(
            loan.tracking_id,
            RepaymentRecord(date=_now(), amount=10000),
        )
        assert updated.outstanding_balance == 40000

    @pytest.mark.asyncio
    async def test_full_repayment_closes_and_emits_event(self, service, events):
        loan = await service.track_loan(
            profile_id="p1", lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=10000, interest_rate_annual=10, tenure_months=6, emi_amount=2000),
            disbursement_date=_now(),
        )
        events.events.clear()

        updated = await service.record_repayment(
            loan.tracking_id,
            RepaymentRecord(date=_now(), amount=10000),
        )
        assert updated.status == LoanStatus.CLOSED
        assert any(e.event_type == "loan.closed" for e in events.events)

    @pytest.mark.asyncio
    async def test_repayment_on_closed_loan_raises(self, service):
        loan = await service.track_loan(
            profile_id="p1", lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=10000, interest_rate_annual=10, tenure_months=6, emi_amount=2000),
            disbursement_date=_now(),
        )
        await service.record_repayment(
            loan.tracking_id, RepaymentRecord(date=_now(), amount=10000),
        )
        with pytest.raises(ValueError, match="closed"):
            await service.record_repayment(
                loan.tracking_id, RepaymentRecord(date=_now(), amount=1000),
            )

    @pytest.mark.asyncio
    async def test_repayment_not_found_raises(self, service):
        with pytest.raises(KeyError):
            await service.record_repayment(
                "nonexistent", RepaymentRecord(date=_now(), amount=1000),
            )


class TestStatusUpdate:
    @pytest.mark.asyncio
    async def test_status_change_emits_event(self, service, events):
        loan = await service.track_loan(
            profile_id="p1", lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=50000, interest_rate_annual=10, tenure_months=12, emi_amount=4500),
            disbursement_date=_now(),
        )
        events.events.clear()

        updated = await service.update_loan_status(loan.tracking_id, LoanStatus.DEFAULTED)
        assert updated.status == LoanStatus.DEFAULTED
        assert events.events[0].event_type == "loan.status_changed"
        assert events.events[0].payload["old_status"] == "ACTIVE"
        assert events.events[0].payload["new_status"] == "DEFAULTED"


class TestExposureQueries:
    @pytest.mark.asyncio
    async def test_exposure_with_multiple_loans(self, service):
        for lender, src, principal in [
            ("SBI", LoanSourceType.FORMAL, 100000),
            ("SHG", LoanSourceType.SEMI_FORMAL, 30000),
            ("Local", LoanSourceType.INFORMAL, 20000),
        ]:
            await service.track_loan(
                profile_id="p1", lender_name=lender,
                source_type=src,
                terms=LoanTerms(principal=principal, interest_rate_annual=12, tenure_months=12, emi_amount=principal // 12),
                disbursement_date=_now(),
            )

        exposure = await service.get_total_exposure("p1", annual_income=120000)
        assert exposure.total_outstanding == 150000
        assert exposure.active_loan_count == 3
        assert len(exposure.by_source) == 3

        # P4: sum of sources == total
        source_sum = sum(s.total_outstanding for s in exposure.by_source)
        assert source_sum == pytest.approx(exposure.total_outstanding)

    @pytest.mark.asyncio
    async def test_dti_ratio(self, service):
        await service.track_loan(
            profile_id="p1", lender_name="SBI",
            source_type=LoanSourceType.FORMAL,
            terms=LoanTerms(principal=120000, interest_rate_annual=12, tenure_months=12, emi_amount=10000),
            disbursement_date=_now(),
        )
        dti = await service.get_debt_to_income_ratio("p1", annual_income=120000)
        # EMI 10000 / monthly income 10000 = 1.0
        assert dti == pytest.approx(1.0)
