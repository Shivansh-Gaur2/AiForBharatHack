"""Domain interfaces (ports) for the Risk Assessment service."""

from __future__ import annotations

from typing import Protocol

from services.shared.models import ProfileId

from .models import RiskAssessment


class RiskAssessmentRepository(Protocol):
    """Port: persistence for risk assessments."""

    async def save(self, assessment: RiskAssessment) -> None: ...

    async def find_latest(self, profile_id: ProfileId) -> RiskAssessment | None: ...

    async def find_by_id(self, assessment_id: str) -> RiskAssessment | None: ...

    async def find_history(
        self,
        profile_id: ProfileId,
        limit: int = 10,
    ) -> list[RiskAssessment]: ...

    async def delete_by_profile(self, profile_id: ProfileId) -> int: ...


class ProfileDataProvider(Protocol):
    """Port: fetches profile data needed for risk scoring.

    This abstracts cross-service data access so the domain layer
    doesn't know whether it's an HTTP call, event replay, or local query.
    """

    async def get_income_volatility(self, profile_id: ProfileId) -> dict: ...
    async def get_personal_info(self, profile_id: ProfileId) -> dict: ...


class LoanDataProvider(Protocol):
    """Port: fetches loan/exposure data for risk scoring."""

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict: ...
    async def get_repayment_stats(self, profile_id: ProfileId) -> dict: ...
