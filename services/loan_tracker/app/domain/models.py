"""Loan Tracker domain entities — pure Python, zero infrastructure imports.

These are rich domain objects modelling multi-loan tracking, exposure
aggregation, and debt-to-income calculation for rural borrowers.

Design doc ref: §4 Multi-Loan Tracker
Properties validated: P4 (Multi-Loan Aggregation), P5 (Real-time Updates)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from services.shared.models import (
    LoanSourceType,
    LoanStatus,
    ProfileId,
    TrackingId,
    generate_id,
)


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoanTerms:
    """Negotiated terms of a loan."""
    principal: float
    interest_rate_annual: float        # % per annum
    tenure_months: int
    emi_amount: float                  # monthly instalment (0 for bullet)
    collateral_description: str | None = None


@dataclass(frozen=True)
class RepaymentRecord:
    """A single repayment event."""
    date: datetime
    amount: float
    is_late: bool = False
    days_overdue: int = 0


@dataclass(frozen=True)
class SourceExposure:
    """Aggregated exposure for one loan-source type."""
    source_type: LoanSourceType
    total_outstanding: float
    loan_count: int
    weighted_avg_interest: float       # weighted by outstanding amount


# ---------------------------------------------------------------------------
# Loan Aggregate
# ---------------------------------------------------------------------------
@dataclass
class Loan:
    """A single tracked loan (aggregate root for one loan)."""
    tracking_id: TrackingId
    profile_id: ProfileId
    lender_name: str
    source_type: LoanSourceType
    terms: LoanTerms
    status: LoanStatus
    disbursement_date: datetime
    maturity_date: datetime | None = None
    outstanding_balance: float = 0.0
    total_repaid: float = 0.0
    repayments: list[RepaymentRecord] = field(default_factory=list)
    purpose: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # -- Behaviour ---------------------------------------------------------

    def record_repayment(self, repayment: RepaymentRecord) -> None:
        """Record a repayment and update the outstanding balance."""
        self.repayments.append(repayment)
        self.total_repaid += repayment.amount
        self.outstanding_balance = max(0.0, self.outstanding_balance - repayment.amount)
        self.updated_at = datetime.now(UTC)

        # Auto-close when fully repaid
        if self.outstanding_balance <= 0:
            self.status = LoanStatus.CLOSED

    def update_status(self, new_status: LoanStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def get_repayment_rate(self) -> float:
        """Fraction of principal repaid (0.0 → 1.0)."""
        if self.terms.principal <= 0:
            return 0.0
        return min(1.0, self.total_repaid / self.terms.principal)

    def get_on_time_ratio(self) -> float:
        """Fraction of repayments made on time."""
        if not self.repayments:
            return 1.0
        on_time = sum(1 for r in self.repayments if not r.is_late)
        return on_time / len(self.repayments)

    def get_monthly_obligation(self) -> float:
        """Monthly payment obligation for this loan."""
        if self.status in (LoanStatus.CLOSED, LoanStatus.DEFAULTED):
            return 0.0
        return self.terms.emi_amount

    @staticmethod
    def create(
        profile_id: ProfileId,
        lender_name: str,
        source_type: LoanSourceType,
        terms: LoanTerms,
        disbursement_date: datetime,
        maturity_date: datetime | None = None,
        purpose: str = "",
        notes: str = "",
    ) -> Loan:
        now = datetime.now(UTC)
        return Loan(
            tracking_id=generate_id(),
            profile_id=profile_id,
            lender_name=lender_name,
            source_type=source_type,
            terms=terms,
            status=LoanStatus.ACTIVE,
            disbursement_date=disbursement_date,
            maturity_date=maturity_date,
            outstanding_balance=terms.principal,
            total_repaid=0.0,
            repayments=[],
            purpose=purpose,
            notes=notes,
            created_at=now,
            updated_at=now,
        )


# ---------------------------------------------------------------------------
# Debt Exposure Aggregate (read-model, computed from loans)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DebtExposure:
    """Aggregated debt exposure for a borrower (Property 4).

    Invariant: total_outstanding == sum of outstanding across all source types.
    """
    profile_id: ProfileId
    total_outstanding: float
    monthly_obligations: float
    debt_to_income_ratio: float
    credit_utilisation: float       # outstanding / total_sanctioned
    by_source: list[SourceExposure]
    active_loan_count: int
    total_loan_count: int
    computed_at: datetime

    @staticmethod
    def compute(
        loans: list[Loan],
        profile_id: ProfileId,
        annual_income: float,
    ) -> DebtExposure:
        """Compute exposure from a list of loans (Property 4).

        The total across sources MUST equal the overall total — this is the
        core aggregation-accuracy invariant.
        """
        now = datetime.now(UTC)

        if not loans:
            return DebtExposure(
                profile_id=profile_id,
                total_outstanding=0.0,
                monthly_obligations=0.0,
                debt_to_income_ratio=0.0,
                credit_utilisation=0.0,
                by_source=[],
                active_loan_count=0,
                total_loan_count=0,
                computed_at=now,
            )

        active_loans = [l for l in loans if l.status == LoanStatus.ACTIVE]

        # Group by source type
        by_source: dict[LoanSourceType, list[Loan]] = {}
        for loan in active_loans:
            by_source.setdefault(loan.source_type, []).append(loan)

        source_exposures: list[SourceExposure] = []
        for src_type, src_loans in by_source.items():
            total_out = sum(l.outstanding_balance for l in src_loans)
            # Weighted average interest rate (weighted by outstanding)
            if total_out > 0:
                wavg = sum(
                    l.terms.interest_rate_annual * l.outstanding_balance
                    for l in src_loans
                ) / total_out
            else:
                wavg = 0.0
            source_exposures.append(SourceExposure(
                source_type=src_type,
                total_outstanding=round(total_out, 2),
                loan_count=len(src_loans),
                weighted_avg_interest=round(wavg, 2),
            ))

        total_outstanding = sum(se.total_outstanding for se in source_exposures)
        monthly_obligations = sum(l.get_monthly_obligation() for l in active_loans)
        total_sanctioned = sum(l.terms.principal for l in active_loans)

        monthly_income = annual_income / 12 if annual_income > 0 else 0
        dti = (monthly_obligations / monthly_income) if monthly_income > 0 else 0.0
        util = (total_outstanding / total_sanctioned) if total_sanctioned > 0 else 0.0

        return DebtExposure(
            profile_id=profile_id,
            total_outstanding=round(total_outstanding, 2),
            monthly_obligations=round(monthly_obligations, 2),
            debt_to_income_ratio=round(dti, 4),
            credit_utilisation=round(util, 4),
            by_source=source_exposures,
            active_loan_count=len(active_loans),
            total_loan_count=len(loans),
            computed_at=now,
        )
