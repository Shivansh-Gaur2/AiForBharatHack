"""In-memory repository implementation for the Early Warning service.

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.early_warning.app.domain.models import Alert, AlertStatus, SimulationResult
from services.shared.models import ProfileId


class InMemoryAlertRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        # alert_id → Alert
        self._alerts: dict[str, Alert] = {}
        # profile_id → list[alert_id] (insertion order)
        self._alerts_by_profile: dict[ProfileId, list[str]] = {}

        # simulation_id → SimulationResult
        self._simulations: dict[str, SimulationResult] = {}
        # profile_id → list[simulation_id] (insertion order)
        self._simulations_by_profile: dict[ProfileId, list[str]] = {}

    # ------------------------------------------------------------------
    # AlertRepository protocol (all async)
    # ------------------------------------------------------------------

    async def save_alert(self, alert: Alert) -> None:
        self._alerts[alert.alert_id] = alert
        bucket = self._alerts_by_profile.setdefault(alert.profile_id, [])
        if alert.alert_id not in bucket:
            bucket.append(alert.alert_id)

    async def find_alert_by_id(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    async def find_alerts_by_profile(
        self, profile_id: ProfileId, limit: int = 50,
    ) -> list[Alert]:
        ids = self._alerts_by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]  # most recent first
        return [self._alerts[aid] for aid in recent if aid in self._alerts]

    async def find_active_alerts(self, profile_id: ProfileId) -> list[Alert]:
        ids = self._alerts_by_profile.get(profile_id, [])
        return [
            self._alerts[aid]
            for aid in reversed(ids)
            if aid in self._alerts
            and self._alerts[aid].status == AlertStatus.ACTIVE
        ]

    async def save_simulation(self, result: SimulationResult) -> None:
        self._simulations[result.simulation_id] = result
        bucket = self._simulations_by_profile.setdefault(result.profile_id, [])
        if result.simulation_id not in bucket:
            bucket.append(result.simulation_id)

    async def find_simulation_by_id(self, simulation_id: str) -> SimulationResult | None:
        return self._simulations.get(simulation_id)

    async def find_simulations_by_profile(
        self, profile_id: ProfileId, limit: int = 20,
    ) -> list[SimulationResult]:
        ids = self._simulations_by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]
        return [self._simulations[sid] for sid in recent if sid in self._simulations]

    async def delete_by_profile(self, profile_id: ProfileId) -> int:
        count = 0
        alert_ids = self._alerts_by_profile.pop(profile_id, [])
        for aid in alert_ids:
            self._alerts.pop(aid, None)
            count += 1
        sim_ids = self._simulations_by_profile.pop(profile_id, [])
        for sid in sim_ids:
            self._simulations.pop(sid, None)
            count += 1
        return count
