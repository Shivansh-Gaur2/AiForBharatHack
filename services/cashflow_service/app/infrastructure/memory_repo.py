"""In-memory repository implementation for the Cash Flow service.

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.cashflow_service.app.domain.models import CashFlowForecast, CashFlowRecord
from services.shared.models import ProfileId


class InMemoryCashFlowRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        # forecast_id → CashFlowForecast
        self._forecasts: dict[str, CashFlowForecast] = {}
        # profile_id → list[forecast_id]  (insertion order = time order)
        self._forecasts_by_profile: dict[ProfileId, list[str]] = {}

        # record_id → CashFlowRecord
        self._records: dict[str, CashFlowRecord] = {}
        # profile_id → list[record_id]
        self._records_by_profile: dict[ProfileId, list[str]] = {}

    # ------------------------------------------------------------------
    # CashFlowRepository protocol (all async)
    # ------------------------------------------------------------------

    async def save_forecast(self, forecast: CashFlowForecast) -> None:
        self._forecasts[forecast.forecast_id] = forecast
        bucket = self._forecasts_by_profile.setdefault(forecast.profile_id, [])
        if forecast.forecast_id not in bucket:
            bucket.append(forecast.forecast_id)

    async def find_forecast_by_id(self, forecast_id: str) -> CashFlowForecast | None:
        return self._forecasts.get(forecast_id)

    async def find_latest_forecast(self, profile_id: ProfileId) -> CashFlowForecast | None:
        ids = self._forecasts_by_profile.get(profile_id, [])
        if not ids:
            return None
        return self._forecasts.get(ids[-1])

    async def find_forecast_history(
        self, profile_id: ProfileId, limit: int = 10,
    ) -> list[CashFlowForecast]:
        ids = self._forecasts_by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]
        return [self._forecasts[fid] for fid in recent if fid in self._forecasts]

    async def save_record(self, record: CashFlowRecord) -> None:
        self._records[record.record_id] = record
        bucket = self._records_by_profile.setdefault(record.profile_id, [])
        if record.record_id not in bucket:
            bucket.append(record.record_id)

    async def save_records(self, records: list[CashFlowRecord]) -> None:
        for record in records:
            await self.save_record(record)

    async def find_records_by_profile(
        self, profile_id: ProfileId, limit: int = 200,
    ) -> list[CashFlowRecord]:
        ids = self._records_by_profile.get(profile_id, [])
        recent = ids[-limit:]
        return [self._records[rid] for rid in recent if rid in self._records]
