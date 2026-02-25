"""Unit tests for Loan domain models — DebtExposure and Loan behaviour."""

from datetime import UTC, datetime

import pytest

from services.loan_tracker.app.domain.models import (
    DebtExposure,
    Loan,
    LoanTerms,
    RepaymentRecord,
)
from services.shared.models import LoanSourceType, LoanStatus


def _make_terms(**overrides) -> LoanTerms:
    defaults = {
        "principal": 50000,
        "interest_rate_annual": 12.0,
        "tenure_months": 12,
        "emi_amount": 4500,
    }
    defaults.update(overrides)
    return LoanTerms(**defaults)


def _make_loan(**overrides) -> Loan:
    now = datetime.now(UTC)
    return Loan.create(
        profile_id=overrides.pop("profile_id", "profile-1"),
        lender_name=overrides.pop("lender_name", "SBI"),
        source_type=overrides.pop("source_type", LoanSourceType.FORMAL),
        terms=overrides.pop("terms", _make_terms()),
        disbursement_date=overrides.pop("disbursement_date", now),
    )


class TestLoanCreation:
    def test_create_sets_active_status(self):
        loan = _make_loan()
        assert loan.status == LoanStatus.ACTIVE
        assert loan.outstanding_balance == 50000
        assert loan.total_repaid == 0.0
        assert loan.tracking_id is not None

    def test_create_sets_outstanding_to_principal(self):
        terms = _make_terms(principal=100000)
        loan = _make_loan(terms=terms)
        assert loan.outstanding_balance == 100000


class TestLoanRepayment:
    def test_repayment_reduces_outstanding(self):
        loan = _make_loan()
        repayment = RepaymentRecord(
            date=datetime.now(UTC), amount=10000,
        )
        loan.record_repayment(repayment)
        assert loan.outstanding_balance == 40000
        assert loan.total_repaid == 10000
        assert len(loan.repayments) == 1

    def test_full_repayment_closes_loan(self):
        loan = _make_loan()
        loan.record_repayment(RepaymentRecord(
            date=datetime.now(UTC), amount=50000,
        ))
        assert loan.status == LoanStatus.CLOSED
        assert loan.outstanding_balance == 0

    def test_multiple_repayments_accumulate(self):
        loan = _make_loan()
        for _ in range(5):
            loan.record_repayment(RepaymentRecord(
                date=datetime.now(UTC), amount=10000,
            ))
        assert loan.outstanding_balance == 0
        assert loan.total_repaid == 50000
        assert loan.status == LoanStatus.CLOSED

    def test_repayment_rate(self):
        loan = _make_loan()
        loan.record_repayment(RepaymentRecord(
            date=datetime.now(UTC), amount=25000,
        ))
        assert loan.get_repayment_rate() == pytest.approx(0.5)

    def test_on_time_ratio(self):
        loan = _make_loan()
        loan.record_repayment(RepaymentRecord(
            date=datetime.now(UTC), amount=5000, is_late=False,
        ))
        loan.record_repayment(RepaymentRecord(
            date=datetime.now(UTC), amount=5000, is_late=True, days_overdue=5,
        ))
        assert loan.get_on_time_ratio() == pytest.approx(0.5)


class TestLoanStatus:
    def test_update_status(self):
        loan = _make_loan()
        loan.update_status(LoanStatus.RESTRUCTURED)
        assert loan.status == LoanStatus.RESTRUCTURED

    def test_closed_loan_has_zero_obligation(self):
        loan = _make_loan()
        loan.update_status(LoanStatus.CLOSED)
        assert loan.get_monthly_obligation() == 0.0

    def test_defaulted_loan_has_zero_obligation(self):
        loan = _make_loan()
        loan.update_status(LoanStatus.DEFAULTED)
        assert loan.get_monthly_obligation() == 0.0

    def test_active_loan_has_emi_obligation(self):
        loan = _make_loan()
        assert loan.get_monthly_obligation() == 4500


class TestDebtExposure:
    """Property 4: Multi-Loan Aggregation Accuracy."""

    def test_empty_loans_zero_exposure(self):
        exposure = DebtExposure.compute([], "p1", 100000)
        assert exposure.total_outstanding == 0
        assert exposure.monthly_obligations == 0
        assert exposure.debt_to_income_ratio == 0
        assert exposure.active_loan_count == 0

    def test_single_loan_exposure(self):
        loan = _make_loan(profile_id="p1")
        exposure = DebtExposure.compute([loan], "p1", 120000)
        assert exposure.total_outstanding == 50000
        assert exposure.monthly_obligations == 4500
        assert exposure.active_loan_count == 1
        assert exposure.total_loan_count == 1

    def test_multi_source_aggregation_accuracy(self):
        """P4: total == sum of all sources."""
        formal = _make_loan(
            profile_id="p1",
            source_type=LoanSourceType.FORMAL,
            terms=_make_terms(principal=100000, emi_amount=9000),
            lender_name="SBI",
        )
        semiformal = _make_loan(
            profile_id="p1",
            source_type=LoanSourceType.SEMI_FORMAL,
            terms=_make_terms(principal=30000, emi_amount=3000),
            lender_name="SHG",
        )
        informal = _make_loan(
            profile_id="p1",
            source_type=LoanSourceType.INFORMAL,
            terms=_make_terms(principal=20000, emi_amount=2500),
            lender_name="Moneylender",
        )

        exposure = DebtExposure.compute(
            [formal, semiformal, informal], "p1", 120000,
        )

        # P4 invariant: total == sum of source totals
        source_sum = sum(s.total_outstanding for s in exposure.by_source)
        assert exposure.total_outstanding == pytest.approx(source_sum)
        assert exposure.total_outstanding == 150000
        assert exposure.monthly_obligations == 14500
        assert exposure.active_loan_count == 3

    def test_closed_loans_excluded_from_exposure(self):
        active = _make_loan(profile_id="p1")
        closed = _make_loan(profile_id="p1")
        closed.update_status(LoanStatus.CLOSED)

        exposure = DebtExposure.compute([active, closed], "p1", 120000)
        assert exposure.active_loan_count == 1
        assert exposure.total_loan_count == 2
        assert exposure.total_outstanding == 50000

    def test_debt_to_income_ratio_calculation(self):
        loan = _make_loan(
            profile_id="p1",
            terms=_make_terms(principal=100000, emi_amount=10000),
        )
        exposure = DebtExposure.compute([loan], "p1", 120000)
        # DTI = 10000 / (120000/12) = 10000 / 10000 = 1.0
        assert exposure.debt_to_income_ratio == pytest.approx(1.0)

    def test_credit_utilisation(self):
        loan = _make_loan(profile_id="p1")
        # Repay half
        loan.record_repayment(RepaymentRecord(
            date=datetime.now(UTC), amount=25000,
        ))
        exposure = DebtExposure.compute([loan], "p1", 120000)
        assert exposure.credit_utilisation == pytest.approx(0.5)

    def test_weighted_avg_interest(self):
        l1 = _make_loan(
            source_type=LoanSourceType.FORMAL,
            terms=_make_terms(principal=100000, interest_rate_annual=10.0),
        )
        l2 = _make_loan(
            source_type=LoanSourceType.FORMAL,
            terms=_make_terms(principal=50000, interest_rate_annual=16.0),
        )
        exposure = DebtExposure.compute([l1, l2], "p1", 200000)

        formal_source = next(s for s in exposure.by_source if s.source_type == LoanSourceType.FORMAL)
        # Weighted avg: (100000*10 + 50000*16) / 150000 = 12.0
        assert formal_source.weighted_avg_interest == pytest.approx(12.0)
