"""Port interfaces for the Guidance Service.

All ports are Protocol classes — infrastructure adapters implement them.
Domain code depends only on these abstractions.
"""

from __future__ import annotations

from typing import Protocol

from services.shared.models import ProfileId

from .models import CreditGuidance

# ---------------------------------------------------------------------------
# Repository Ports
# ---------------------------------------------------------------------------


class GuidanceRepository(Protocol):
    """Persistence port for credit guidance records."""

    async def save_guidance(self, guidance: CreditGuidance) -> None: ...

    async def find_guidance_by_id(self, guidance_id: str) -> CreditGuidance | None: ...

    async def find_guidance_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 20,
    ) -> list[CreditGuidance]: ...

    async def find_active_guidance(
        self,
        profile_id: ProfileId,
    ) -> list[CreditGuidance]: ...


# ---------------------------------------------------------------------------
# Cross-Service Data Provider Ports
# ---------------------------------------------------------------------------


class RiskDataProvider(Protocol):
    """Fetches risk assessment data from the Risk Assessment service."""

    async def get_risk_category(self, profile_id: ProfileId) -> str:
        """Returns risk category: LOW, MEDIUM, HIGH, VERY_HIGH."""
        ...

    async def get_risk_score(self, profile_id: ProfileId) -> float:
        """Returns the raw risk score (0-1000)."""
        ...


class CashFlowDataProvider(Protocol):
    """Fetches cash flow data from the Cash Flow service."""

    async def get_forecast_projections(
        self,
        profile_id: ProfileId,
    ) -> list[tuple[int, int, float, float]]:
        """Returns baseline projections: [(month, year, inflow, outflow), ...]."""
        ...

    async def get_repayment_capacity(
        self,
        profile_id: ProfileId,
    ) -> dict:
        """Returns repayment capacity dict with recommended_emi, max_emi, etc."""
        ...


class LoanDataProvider(Protocol):
    """Fetches loan data from the Loan Tracker service."""

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        """Returns debt exposure dict: dti_ratio, total_outstanding, monthly_obligations, etc."""
        ...


class ProfileDataProvider(Protocol):
    """Fetches profile data from the Profile service."""

    async def get_profile_summary(self, profile_id: ProfileId) -> dict:
        """Returns profile summary: occupation, land_holding, household_size, etc."""
        ...

    async def get_household_expense(self, profile_id: ProfileId) -> float:
        """Returns estimated monthly household expense."""
        ...


class AlertDataProvider(Protocol):
    """Fetches alert data from the Early Warning service."""

    async def get_active_alerts(self, profile_id: ProfileId) -> list[dict]:
        """Returns active alerts for the profile."""
        ...


class AIExplanationProvider(Protocol):
    """Generates AI-enriched natural-language summaries via an LLM.

    The service calls this *after* computing the template-based guidance so
    that the AI summary is purely additive — the system still works if this
    provider is absent or unavailable.
    """

    async def generate_summary(self, context: dict) -> str | None:
        """Return an AI-generated summary string, or None on failure."""
        ...
