"""Profile domain service — orchestrates business logic.

This is the entry point for all profile operations. It depends on
abstract ports (ProfileRepository, EventPublisher) injected at runtime.
"""

from __future__ import annotations

import logging

from services.shared.events import DomainEvent, EventPublisher
from services.shared.models import ProfileId

from .interfaces import ProfileRepository
from .models import (
    BorrowerProfile,
    ExpenseRecord,
    IncomeRecord,
    LivelihoodInfo,
    PersonalInfo,
    SeasonalFactor,
    VolatilityMetrics,
)
from .validators import (
    validate_income_records,
    validate_livelihood_info,
    validate_personal_info,
    validate_profile_for_creation,
)

logger = logging.getLogger(__name__)


class ProfileService:
    """Domain service — pure business logic orchestration.

    Dependencies are injected via constructor (Ports & Adapters pattern).
    """

    def __init__(
        self,
        repository: ProfileRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repo = repository
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def create_profile(
        self,
        personal_info: PersonalInfo,
        livelihood_info: LivelihoodInfo,
        income_records: list[IncomeRecord] | None = None,
        expense_records: list[ExpenseRecord] | None = None,
        seasonal_factors: list[SeasonalFactor] | None = None,
    ) -> BorrowerProfile:
        """Create a new borrower profile with full validation.

        Raises ValueError if validation fails.
        """
        income_records = income_records or []
        expense_records = expense_records or []
        seasonal_factors = seasonal_factors or []

        # Validate all inputs
        validation = validate_profile_for_creation(
            personal_info, livelihood_info, income_records
        )
        if not validation.is_valid:
            error_msgs = "; ".join(e.message for e in validation.errors)
            raise ValueError(f"Profile validation failed: {error_msgs}")

        # Create the aggregate
        profile = BorrowerProfile.create(
            personal_info=personal_info,
            livelihood_info=livelihood_info,
            income_records=income_records,
            expense_records=expense_records,
            seasonal_factors=seasonal_factors,
        )

        # Persist
        self._repo.save(profile)

        # Publish domain event
        self._events.publish(DomainEvent(
            event_type="profile.created",
            aggregate_id=profile.profile_id,
            payload={
                "profile_id": profile.profile_id,
                "occupation": personal_info.name,
                "district": personal_info.district,
                "state": personal_info.state,
            },
        ))

        logger.info("Created profile %s", profile.profile_id)
        return profile

    def update_personal_info(
        self, profile_id: ProfileId, personal_info: PersonalInfo
    ) -> BorrowerProfile:
        """Update personal information of an existing profile."""
        profile = self._get_profile_or_raise(profile_id)

        validation = validate_personal_info(personal_info)
        if not validation.is_valid:
            error_msgs = "; ".join(e.message for e in validation.errors)
            raise ValueError(f"Validation failed: {error_msgs}")

        profile.update_personal_info(personal_info)
        self._repo.save(profile)

        self._events.publish(DomainEvent(
            event_type="profile.updated",
            aggregate_id=profile_id,
            payload={"updated_fields": ["personal_info"]},
        ))

        return profile

    def update_livelihood_info(
        self, profile_id: ProfileId, livelihood_info: LivelihoodInfo
    ) -> BorrowerProfile:
        """Update livelihood information."""
        profile = self._get_profile_or_raise(profile_id)

        validation = validate_livelihood_info(livelihood_info)
        if not validation.is_valid:
            error_msgs = "; ".join(e.message for e in validation.errors)
            raise ValueError(f"Validation failed: {error_msgs}")

        profile.update_livelihood_info(livelihood_info)
        self._repo.save(profile)

        self._events.publish(DomainEvent(
            event_type="profile.updated",
            aggregate_id=profile_id,
            payload={"updated_fields": ["livelihood_info"]},
        ))

        return profile

    def add_income_records(
        self, profile_id: ProfileId, records: list[IncomeRecord]
    ) -> BorrowerProfile:
        """Add income records and recompute volatility metrics."""
        profile = self._get_profile_or_raise(profile_id)

        validation = validate_income_records(records)
        if not validation.is_valid:
            error_msgs = "; ".join(e.message for e in validation.errors)
            raise ValueError(f"Validation failed: {error_msgs}")

        # Preserve historical records (Requirement 1.5)
        profile.add_income_records(records)
        self._repo.save(profile)

        self._events.publish(DomainEvent(
            event_type="profile.income_updated",
            aggregate_id=profile_id,
            payload={
                "records_added": len(records),
                "new_volatility": profile.volatility_metrics.volatility_category
                if profile.volatility_metrics else "UNKNOWN",
            },
        ))

        return profile

    def add_expense_records(
        self, profile_id: ProfileId, records: list[ExpenseRecord]
    ) -> BorrowerProfile:
        """Add expense records."""
        profile = self._get_profile_or_raise(profile_id)
        profile.add_expense_records(records)
        self._repo.save(profile)
        return profile

    def set_seasonal_factors(
        self, profile_id: ProfileId, factors: list[SeasonalFactor]
    ) -> BorrowerProfile:
        """Set seasonal adjustment factors."""
        profile = self._get_profile_or_raise(profile_id)
        profile.set_seasonal_factors(factors)
        self._repo.save(profile)
        return profile

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: ProfileId) -> BorrowerProfile:
        """Retrieve a profile by ID."""
        return self._get_profile_or_raise(profile_id)

    def get_volatility_metrics(self, profile_id: ProfileId) -> VolatilityMetrics:
        """Get income volatility metrics for a profile."""
        profile = self._get_profile_or_raise(profile_id)
        if profile.volatility_metrics is None:
            raise ValueError(
                f"No volatility data for profile {profile_id}. "
                "Add income records first."
            )
        return profile.volatility_metrics

    def calculate_income_volatility(
        self, profile_id: ProfileId
    ) -> VolatilityMetrics:
        """Force-recalculate volatility metrics from current income records."""
        profile = self._get_profile_or_raise(profile_id)
        monthly_incomes = profile.get_monthly_incomes()
        if not monthly_incomes:
            raise ValueError("Cannot compute volatility without income records")

        metrics = VolatilityMetrics.compute(monthly_incomes)
        profile.volatility_metrics = metrics
        self._repo.save(profile)
        return metrics

    def delete_profile(self, profile_id: ProfileId) -> None:
        """Permanently delete a borrower profile.

        Raises KeyError if the profile does not exist.
        """
        self._get_profile_or_raise(profile_id)  # ensures 404 if missing
        self._repo.delete(profile_id)

        self._events.publish(DomainEvent(
            event_type="profile.deleted",
            aggregate_id=profile_id,
            payload={"profile_id": profile_id},
        ))

        logger.info("Deleted profile %s", profile_id)

    def list_profiles(
        self, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[BorrowerProfile], str | None]:
        """List profiles with cursor-based pagination."""
        return self._repo.list_all(limit=limit, cursor=cursor)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_profile_or_raise(self, profile_id: ProfileId) -> BorrowerProfile:
        profile = self._repo.find_by_id(profile_id)
        if profile is None:
            raise KeyError(f"Profile not found: {profile_id}")
        return profile
