"""Port interfaces for the Early Warning & Scenario service.

All ports are Protocol classes — infrastructure adapters implement them.
Domain code depends only on these abstractions.
"""

from __future__ import annotations

from typing import Protocol

from services.shared.models import ProfileId

from .models import Alert, SimulationResult


# ---------------------------------------------------------------------------
# Repository Ports
# ---------------------------------------------------------------------------
class AlertRepository(Protocol):
    """Persistence port for alerts."""

    async def save_alert(self, alert: Alert) -> None: ...

    async def find_alert_by_id(self, alert_id: str) -> Alert | None: ...

    async def find_alerts_by_profile(
        self, profile_id: ProfileId, limit: int = 50,
    ) -> list[Alert]: ...

    async def find_active_alerts(
        self, profile_id: ProfileId,
    ) -> list[Alert]: ...

    async def save_simulation(self, result: SimulationResult) -> None: ...

    async def find_simulation_by_id(self, simulation_id: str) -> SimulationResult | None: ...

    async def find_simulations_by_profile(
        self, profile_id: ProfileId, limit: int = 20,
    ) -> list[SimulationResult]: ...


# ---------------------------------------------------------------------------
# Cross-Service Data Provider Ports
# ---------------------------------------------------------------------------
class RiskDataProvider(Protocol):
    """Fetches risk assessment data from the Risk Assessment service."""

    async def get_latest_risk_category(self, profile_id: ProfileId) -> str | None:
        """Returns risk category string: LOW, MEDIUM, HIGH, VERY_HIGH or None."""
        ...

    async def get_risk_score(self, profile_id: ProfileId) -> float:
        """Returns the raw risk score (0–1000)."""
        ...


class CashFlowDataProvider(Protocol):
    """Fetches cash flow data from the Cash Flow service."""

    async def get_latest_forecast_projections(
        self, profile_id: ProfileId,
    ) -> list[tuple[int, int, float, float]]:
        """Returns baseline projections: [(month, year, inflow, outflow), ...]."""
        ...

    async def get_repayment_capacity(
        self, profile_id: ProfileId,
    ) -> dict:
        """Returns repayment capacity dict with recommended_emi, max_emi, etc."""
        ...


class LoanDataProvider(Protocol):
    """Fetches loan data from the Loan Tracker service."""

    async def get_debt_exposure(self, profile_id: ProfileId) -> dict:
        """Returns debt exposure dict with dti_ratio, total_outstanding, etc."""
        ...

    async def get_repayment_stats(self, profile_id: ProfileId) -> dict:
        """Returns repayment stats: missed_payments, days_overdue_avg, on_time_ratio."""
        ...


class ProfileDataProvider(Protocol):
    """Fetches profile data from the Profile service."""

    async def get_actual_incomes(
        self, profile_id: ProfileId,
    ) -> list[tuple[int, int, float]]:
        """Returns actual income entries: [(month, year, amount), ...]."""
        ...

    async def get_household_expense(self, profile_id: ProfileId) -> float:
        """Returns monthly household expense estimate."""
        ...

    async def get_phone_number(self, profile_id: ProfileId) -> str | None:
        """Returns the borrower's phone number, or None if unavailable."""
        ...

    async def get_preferred_language(self, profile_id: ProfileId) -> str:
        """Returns preferred language code (e.g. 'en', 'hi', 'ta')."""
        ...


# ---------------------------------------------------------------------------
# Notification Ports
# ---------------------------------------------------------------------------
class SmsNotifier(Protocol):
    """Port for sending SMS notifications to borrowers."""

    async def send_alert_sms(
        self,
        phone_number: str,
        message: str,
    ) -> bool:
        """Send an SMS message. Returns True on success."""
        ...
