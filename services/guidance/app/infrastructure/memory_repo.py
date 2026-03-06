"""In-memory repository implementation for the Guidance service.

Default storage backend for local development and testing — no AWS needed.
"""

from __future__ import annotations

from services.guidance.app.domain.models import CreditGuidance, GuidanceStatus
from services.shared.models import ProfileId


class InMemoryGuidanceRepository:
    """Thread-unsafe in-memory store; suitable for single-process local dev."""

    def __init__(self) -> None:
        # guidance_id → CreditGuidance
        self._guidance: dict[str, CreditGuidance] = {}
        # profile_id → list[guidance_id] (insertion order)
        self._by_profile: dict[ProfileId, list[str]] = {}

    # ------------------------------------------------------------------
    # GuidanceRepository protocol (all async)
    # ------------------------------------------------------------------

    async def save_guidance(self, guidance: CreditGuidance) -> None:
        self._guidance[guidance.guidance_id] = guidance
        bucket = self._by_profile.setdefault(guidance.profile_id, [])
        if guidance.guidance_id not in bucket:
            bucket.append(guidance.guidance_id)

    async def find_guidance_by_id(self, guidance_id: str) -> CreditGuidance | None:
        return self._guidance.get(guidance_id)

    async def find_guidance_by_profile(
        self,
        profile_id: ProfileId,
        limit: int = 20,
    ) -> list[CreditGuidance]:
        ids = self._by_profile.get(profile_id, [])
        recent = ids[-limit:][::-1]  # most recent first
        return [self._guidance[gid] for gid in recent if gid in self._guidance]

    async def find_active_guidance(self, profile_id: ProfileId) -> list[CreditGuidance]:
        ids = self._by_profile.get(profile_id, [])
        return [
            self._guidance[gid]
            for gid in reversed(ids)
            if gid in self._guidance
            and self._guidance[gid].status == GuidanceStatus.ACTIVE
        ]
