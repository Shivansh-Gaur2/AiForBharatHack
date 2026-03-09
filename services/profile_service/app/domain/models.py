"""Profile domain entities — pure Python, zero infrastructure imports.

These are rich domain objects with behavior, NOT DTOs.
They enforce business invariants and encapsulate domain logic.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

from services.shared.models import (
    OccupationType,
    ProfileId,
    Season,
    generate_id,
)


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PersonalInfo:
    name: str
    age: int
    gender: str
    district: str
    state: str
    dependents: int
    phone: str | None = None
    location: str = ""


@dataclass(frozen=True)
class LandDetails:
    total_acres: float
    irrigated_acres: float
    rain_fed_acres: float
    ownership_type: str = "OWNED"   # OWNED | LEASED | TENANT


@dataclass(frozen=True)
class CropInfo:
    crop_name: str
    season: Season
    area_acres: float
    expected_yield_quintals: float
    expected_price_per_quintal: float


@dataclass(frozen=True)
class LivestockInfo:
    animal_type: str
    count: int
    monthly_income: float = 0.0
    monthly_expense: float = 0.0


@dataclass(frozen=True)
class MigrationInfo:
    destination: str
    months: list[int]           # months of the year (1-12)
    monthly_income: float


@dataclass(frozen=True)
class BusinessDetails:
    """Business/trade info for non-farming occupations (artisans, traders, etc.)."""
    business_type: str                  # e.g. "Pottery", "Grocery Shop"
    workspace_owned: bool = False
    workspace_description: str = ""     # e.g. "Home workshop", "Rented shop in market"
    monthly_revenue: float = 0.0
    monthly_expenses: float = 0.0
    investment_amount: float = 0.0      # Tools for artisan, inventory for trader
    years_in_business: int = 0


@dataclass(frozen=True)
class LivelihoodInfo:
    primary_occupation: OccupationType
    secondary_occupations: list[OccupationType] = field(default_factory=list)
    land_holding: LandDetails | None = None
    crop_patterns: list[CropInfo] = field(default_factory=list)
    livestock: list[LivestockInfo] = field(default_factory=list)
    migration_patterns: list[MigrationInfo] = field(default_factory=list)
    business_details: BusinessDetails | None = None


@dataclass(frozen=True)
class IncomeRecord:
    month: int
    year: int
    amount: float
    source: str             # "crop_sale", "wage", "livestock", "migration", etc.
    is_verified: bool = False


@dataclass(frozen=True)
class ExpenseRecord:
    month: int
    year: int
    amount: float
    category: str           # "seeds", "fertilizer", "food", "health", "education"


@dataclass(frozen=True)
class SeasonalFactor:
    season: Season
    income_multiplier: float    # 1.0 = baseline; >1 = peak; <1 = lean
    expense_multiplier: float
    notes: str = ""


# ---------------------------------------------------------------------------
# Volatility Metrics (computed from income data)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VolatilityMetrics:
    """Quantifies unpredictability of income streams."""
    coefficient_of_variation: float     # stdev / mean
    income_range_ratio: float           # (max - min) / mean
    seasonal_variance: float            # variance across seasonal averages
    months_below_average: int           # fragility indicator
    volatility_category: str            # LOW | MEDIUM | HIGH

    @staticmethod
    def compute(monthly_incomes: list[float]) -> VolatilityMetrics:
        """Compute volatility metrics from a list of monthly incomes."""
        if len(monthly_incomes) < 2:
            return VolatilityMetrics(
                coefficient_of_variation=0.0,
                income_range_ratio=0.0,
                seasonal_variance=0.0,
                months_below_average=0,
                volatility_category="LOW",
            )

        mean = statistics.mean(monthly_incomes)
        if mean == 0:
            return VolatilityMetrics(
                coefficient_of_variation=0.0,
                income_range_ratio=0.0,
                seasonal_variance=0.0,
                months_below_average=len(monthly_incomes),
                volatility_category="HIGH",
            )

        stdev = statistics.stdev(monthly_incomes)
        cv = stdev / mean
        income_range = max(monthly_incomes) - min(monthly_incomes)
        range_ratio = income_range / mean
        months_below = sum(1 for i in monthly_incomes if i < mean)

        # Seasonal variance: variance of quarterly averages
        quarters = [monthly_incomes[i:i+3] for i in range(0, len(monthly_incomes), 3)]
        quarter_avgs = [statistics.mean(q) for q in quarters if q]
        seasonal_var = statistics.variance(quarter_avgs) if len(quarter_avgs) > 1 else 0.0

        # Classify volatility
        if cv < 0.3:
            category = "LOW"
        elif cv < 0.6:
            category = "MEDIUM"
        else:
            category = "HIGH"

        return VolatilityMetrics(
            coefficient_of_variation=round(cv, 4),
            income_range_ratio=round(range_ratio, 4),
            seasonal_variance=round(seasonal_var, 2),
            months_below_average=months_below,
            volatility_category=category,
        )


# ---------------------------------------------------------------------------
# Aggregate Root — BorrowerProfile
# ---------------------------------------------------------------------------
@dataclass
class BorrowerProfile:
    """Aggregate root for the Profile bounded context.

    Contains all financial identity, livelihood, and income pattern data
    for a rural borrower.
    """
    profile_id: ProfileId
    personal_info: PersonalInfo
    livelihood_info: LivelihoodInfo
    income_records: list[IncomeRecord] = field(default_factory=list)
    expense_records: list[ExpenseRecord] = field(default_factory=list)
    seasonal_factors: list[SeasonalFactor] = field(default_factory=list)
    volatility_metrics: VolatilityMetrics | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # -- Domain behavior ------------------------------------------------

    def add_income_records(self, records: list[IncomeRecord]) -> None:
        """Add income records and recompute volatility."""
        self.income_records.extend(records)
        self._recompute_volatility()
        self._touch()

    def add_expense_records(self, records: list[ExpenseRecord]) -> None:
        """Add expense records."""
        self.expense_records.extend(records)
        self._touch()

    def set_seasonal_factors(self, factors: list[SeasonalFactor]) -> None:
        """Replace seasonal factors."""
        self.seasonal_factors = list(factors)
        self._touch()

    def update_personal_info(self, info: PersonalInfo) -> None:
        """Update personal information."""
        self.personal_info = info
        self._touch()

    def update_livelihood_info(self, info: LivelihoodInfo) -> None:
        """Update livelihood information and recompute volatility."""
        self.livelihood_info = info
        self._recompute_volatility()
        self._touch()

    def get_monthly_incomes(self) -> list[float]:
        """Aggregate income records into per-month totals (most recent 12)."""
        if not self.income_records:
            return []

        monthly: dict[tuple, float] = {}
        for rec in self.income_records:
            key = (rec.year, rec.month)
            monthly[key] = monthly.get(key, 0.0) + rec.amount

        # Sort chronologically and take last 12
        sorted_months = sorted(monthly.keys())
        return [monthly[k] for k in sorted_months[-12:]]

    def get_monthly_expenses(self) -> list[float]:
        """Aggregate expense records into per-month totals (most recent 12)."""
        if not self.expense_records:
            return []

        monthly: dict[tuple, float] = {}
        for rec in self.expense_records:
            key = (rec.year, rec.month)
            monthly[key] = monthly.get(key, 0.0) + rec.amount

        sorted_months = sorted(monthly.keys())
        return [monthly[k] for k in sorted_months[-12:]]

    def get_average_monthly_income(self) -> float:
        """Calculate average monthly income from records."""
        incomes = self.get_monthly_incomes()
        return statistics.mean(incomes) if incomes else 0.0

    def get_average_monthly_expense(self) -> float:
        """Calculate average monthly expense from records."""
        expenses = self.get_monthly_expenses()
        return statistics.mean(expenses) if expenses else 0.0

    def get_monthly_surplus(self) -> float:
        """Average monthly surplus (income - expenses)."""
        return self.get_average_monthly_income() - self.get_average_monthly_expense()

    def estimate_annual_income(self) -> float:
        """Estimate annual income from livelihood info and records."""
        # If we have actual records, use them
        monthly_incomes = self.get_monthly_incomes()
        if len(monthly_incomes) >= 6:
            return statistics.mean(monthly_incomes) * 12

        # Otherwise estimate from livelihood
        total = 0.0
        livelihood = self.livelihood_info

        # Crop income
        for crop in livelihood.crop_patterns:
            total += crop.expected_yield_quintals * crop.expected_price_per_quintal

        # Livestock income
        for livestock in livelihood.livestock:
            total += (livestock.monthly_income - livestock.monthly_expense) * 12

        # Migration income
        for migration in livelihood.migration_patterns:
            total += migration.monthly_income * len(migration.months)

        return total

    # -- Internal -------------------------------------------------------

    def _recompute_volatility(self) -> None:
        """Recompute volatility metrics from current income records."""
        monthly_incomes = self.get_monthly_incomes()
        if monthly_incomes:
            self.volatility_metrics = VolatilityMetrics.compute(monthly_incomes)

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    @staticmethod
    def create(
        personal_info: PersonalInfo,
        livelihood_info: LivelihoodInfo,
        income_records: list[IncomeRecord] | None = None,
        expense_records: list[ExpenseRecord] | None = None,
        seasonal_factors: list[SeasonalFactor] | None = None,
    ) -> BorrowerProfile:
        """Factory method — creates a new profile with computed metrics."""
        profile = BorrowerProfile(
            profile_id=generate_id(),
            personal_info=personal_info,
            livelihood_info=livelihood_info,
        )
        if income_records:
            profile.add_income_records(income_records)
        if expense_records:
            profile.add_expense_records(expense_records)
        if seasonal_factors:
            profile.set_seasonal_factors(seasonal_factors)
        return profile
